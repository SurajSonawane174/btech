"""
ingest.py

Bridges comment_extractor.py's output (final_output.csv per PDF, or master_comments.csv
across all PDFs) into Postgres + Qdrant.

comment_extractor.py writes, per PDF: output/<pdf_stem>/final_output.csv
and, across all PDFs in one run: output/master_comments.csv

Usage:
    python ingest.py --input output/<pdf_stem>/final_output.csv
    python ingest.py --input output/master_comments.csv
    python ingest.py --input output/master_comments.csv --allow-unresolved

Identity rules (see docs/HANDOFF.md, known issue 6.1):
  * one SOURCE FILE (source_file_sha256) is one ingest group; rows of different files are
    never merged because their text, drawing number or ids happen to match;
  * the document/revision a file lands under comes from the extractor's metadata columns
    (praj_document_number, praj_revision_number + their *_source provenance);
  * a file whose drawing number or revision is unresolved is SKIPPED unless
    --allow-unresolved is given; then it gets its own placeholder identity
    (UNRESOLVED-<sha12> / NA-<sha8>) instead of being lumped together with other files;
  * if a revision already holds comments from a DIFFERENT source file, the new file is
    reported as a conflict and not inserted (no silent merge);
  * re-ingesting the same file inserts nothing new (ON CONFLICT DO NOTHING), and counts
    come from SELECTs, not cursor.rowcount;
  * literal "NA" text is kept as text: only empty cells are treated as missing.
"""
import re
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from database import db
from vectordb import qdrant_client as vdb
from vectordb import embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

_HEX12 = re.compile(r"^[0-9A-F]{12}$")


def parse_uid(uid: str):
    """comment_id format: PROJECT-DRAWING-...-page-row-seq (project/drawing sanitized, no dashes)."""
    parts = str(uid).split("-")
    if len(parts) < 4:
        return parts[0] if parts else "UNKNOWN", "UNKNOWN"
    return parts[0], parts[1]


def uid_source_suffix(uid: str) -> Optional[str]:
    """The 12-hex source-file suffix of a current-format id, or None for legacy ids."""
    parts = str(uid).split("-")
    if len(parts) == 7 and _HEX12.match(parts[-1]):
        return parts[-1]
    return None


def read_extractor_csv(path) -> pd.DataFrame:
    """Read extractor output as TEXT. pandas' default turns the literal string 'NA' (used by the
    extractor for an unknown revision / customer number, and possibly real comment text) into
    NaN; here only truly empty cells become missing."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def _first(group: pd.DataFrame, col: str) -> Optional[str]:
    if col not in group:
        return None
    vals = [v for v in group[col].tolist() if isinstance(v, str) and v.strip()]
    return vals[0] if vals else None


def _resolve_identity(group: pd.DataFrame, sha: Optional[str], allow_unresolved: bool):
    """-> (project, drawing, revision, problem). problem is None when the group may be ingested."""
    if "praj_revision_number" in group and group["praj_revision_number"].fillna("").nunique() > 1:
        return None, None, None, "rows of one source file disagree on the revision"
    project = parse_uid(group["comment_id"].iloc[0])[0]
    drawing = _first(group, "praj_document_number")
    revision = _first(group, "praj_revision_number")
    has_provenance = "drawing_number_source" in group and "revision_source" in group
    drawing_unresolved = (not drawing or drawing == "UNKNOWN"
                          or (has_provenance and _first(group, "drawing_number_source") == "unresolved"))
    revision_unresolved = (not revision or revision == "NA"
                           or (has_provenance and _first(group, "revision_source") == "unresolved"))
    if drawing_unresolved or revision_unresolved:
        if not allow_unresolved:
            what = " and ".join(w for w, bad in (("drawing number", drawing_unresolved),
                                                 ("revision", revision_unresolved)) if bad)
            return project, drawing, revision, f"unresolved {what} (use --allow-unresolved to ingest)"
        if not sha:
            return project, drawing, revision, "unresolved metadata and no source_file_sha256 to isolate it"
        if drawing_unresolved:
            drawing = f"UNRESOLVED-{sha[:12].upper()}"
        if revision_unresolved:
            revision = f"NA-{sha[:8].upper()}"
    return project, drawing, revision, None


def ingest_dataframe(df: pd.DataFrame, source_label: str, allow_unresolved: bool = False) -> dict:
    totals = {"groups": 0, "comments": 0, "already_present": 0, "embedded": 0,
              "embedding_failed": 0, "skipped": [], "conflicts": []}
    if df.empty:
        logger.info(f"{source_label}: no rows, skipping")
        return totals

    df = df.copy()
    if "source_file_sha256" in df and df["source_file_sha256"].notna().all():
        keys = df["source_file_sha256"]
    else:
        # legacy output (before source hashes): best available separation, with a warning
        logger.warning(f"{source_label}: no source_file_sha256 column; grouping by "
                       f"{'source_file' if 'source_file' in df else 'comment_id prefix + revision'}"
                       f" (re-extract to get exact source isolation)")
        if "source_file" in df:
            keys = df["source_file"].fillna("")
        else:
            keys = df["comment_id"].map(lambda u: "-".join(parse_uid(u))) + "|" + \
                df.get("praj_revision_number", pd.Series([""] * len(df))).fillna("")

    for key, group in df.groupby(keys, sort=True):
        totals["groups"] += 1
        sha = key if "source_file_sha256" in df and _HEX12.match(str(key)[:12].upper()) else None
        label = _first(group, "source_path") or _first(group, "source_file") or str(key)[:16]
        project, drawing, revision, problem = _resolve_identity(group, sha, allow_unresolved)
        if problem:
            logger.warning(f"SKIP {label}: {problem}")
            totals["skipped"].append({"source": label, "reason": problem})
            continue

        project_id = db.get_or_create_project(project_code=project)
        document_id = db.get_or_create_document(project_id=project_id, drawing_number=drawing)

        existing = db.find_revision(document_id, revision)
        if existing and sha:
            held = {uid_source_suffix(c["comment_uid"]) for c in db.get_comments_by_revision(existing)}
            held.discard(None)
            if held and held != {sha[:12].upper()}:
                msg = (f"revision {project}/{drawing}/{revision} already holds comments from another "
                       f"source file ({', '.join(sorted(held))}); not merged")
                logger.error(f"CONFLICT {label}: {msg}")
                totals["conflicts"].append({"source": label, "reason": msg})
                continue

        revision_id = db.create_revision(
            document_id=document_id,
            praj_revision_number=revision,
            customer_document_number=_first(group, "customer_document_number"),
            customer_revision=_first(group, "customer_revision"),
            source_pdf_path=_first(group, "source_path") or _first(group, "source_file"),
        )

        records = group.to_dict("records")
        inserted = db.insert_comments_bulk(revision_id, records)
        totals["comments"] += inserted
        totals["already_present"] += len(records) - inserted
        logger.info(f"{label} -> {project}/{drawing}/{revision}: inserted {inserted}, "
                    f"already present {len(records) - inserted}")

        # Embed + push to Qdrant. Failures leave rows with embedded=false, so a rerun retries.
        embed_items = []
        for c in db.get_comments_by_revision(revision_id):
            if c["embedded"]:
                continue
            text = c["actual_extracted_comment"]
            try:
                vector = embedder.embed_text(text)
            except Exception as e:
                logger.warning(f"Embedding skipped for {c['id']}: {e}")
                totals["embedding_failed"] += 1
                continue
            embed_items.append({
                "comment_id": c["id"], "vector": vector, "text": text,
                "category": c["comment_category"], "project_id": project_id, "revision_id": revision_id,
                "document_id": document_id, "comment_uid": c.get("comment_uid"),
            })
        if embed_items:
            try:
                vdb.upsert_comment_embeddings_bulk(embed_items)
                db.mark_comments_embedded([i["comment_id"] for i in embed_items])
                totals["embedded"] += len(embed_items)
            except Exception as e:
                logger.error(f"Vector upsert failed for {label} ({e}); rows stay embedded=false")
                totals["embedding_failed"] += len(embed_items)

    return totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="final_output.csv or master_comments.csv")
    parser.add_argument("--allow-unresolved", action="store_true",
                        help="ingest files with unresolved drawing/revision under a per-file placeholder identity")
    args = parser.parse_args()

    db.init_pool()
    vdb.ensure_collections()
    if not embedder.check_ready():
        logger.warning("Ollama embedding model not ready — embeddings will be skipped. "
                        "Run: ollama pull nomic-embed-text")

    df = read_extractor_csv(args.input)
    totals = ingest_dataframe(df, args.input, allow_unresolved=args.allow_unresolved)

    logger.info("=" * 50)
    logger.info(f"Ingestion complete | files={totals['groups']} inserted={totals['comments']} "
                f"already_present={totals['already_present']} embedded={totals['embedded']} "
                f"embedding_failed={totals['embedding_failed']} skipped={len(totals['skipped'])} "
                f"conflicts={len(totals['conflicts'])}")
    for s in totals["skipped"]:
        logger.info(f"  skipped  {s['source']}: {s['reason']}")
    for c in totals["conflicts"]:
        logger.info(f"  conflict {c['source']}: {c['reason']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()

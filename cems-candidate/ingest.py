"""
ingest.py -- load comment_extractor.py output into PostgreSQL (final schema), then sync the
new comments to Qdrant.

    python ingest.py --input output/master_comments.csv --project P-1001 \
                     --supplier "ACME Fabricators" --po PO-4512 [--allow-unresolved] [--no-embed]

--project / --supplier / --po are REQUIRED: the extractor does not produce them; the backend
passes them from the upload form. They are never defaulted.

Rules
  * One SOURCE FILE (source_file_sha256) is one ingest group; different files are never merged.
  * A document revision is one `documents` row, upserted on unique_doc_revision
    (project, document number, revision, supplier, PO). A missing revision is stored as 'NA'.
  * A file whose drawing number is unresolved is SKIPPED unless --allow-unresolved; then it gets
    the placeholder document number UNRESOLVED-<sha12>, never a guessed one.
  * Comments are inserted with ON CONFLICT (comment_id) DO NOTHING: re-ingesting a file adds 0 rows.
  * CONFLICTS (reported, nothing inserted for that file):
      - the same PDF was already ingested under a different document row (e.g. another supplier
        or PO): its comment_ids already exist elsewhere and comment_id is globally unique;
      - the target revision already holds comments from a DIFFERENT source file.
  * Extractor fields are mapped through an explicit allowlist (COMMENT_FIELD_MAP); every other
    column (sr_no, email, annotation_type, comment_source, ...) is dropped, never an error.
  * date_of_comment + time_of_comment -> comment_datetime. Accepted dates: DD/MM/YYYY and
    YYYY-MM-DD only; times HH:MM or HH:MM:SS. Anything else, or a date without a time, is
    stored as NULL (an ambiguous OCR date such as 12-09-2026 is not guessed).
  * Literal "NA" text is kept as text; only empty cells are missing.
"""
import re
import sys
import logging
import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from database import db
from vectordb import comment_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

_HEX12 = re.compile(r"^[0-9A-F]{12}$")
_DMY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_YMD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_TIME = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")

# extractor column -> comments column (allowlist). comment_datetime is derived separately.
COMMENT_FIELD_MAP = {
    "comment_id": "comment_id",
    "page_sheet": "page_sheet",
    "actual_extracted_comment": "actual_extracted_comment",
    "snapshot_file": "snapshot_file",
    "name_of_person_commented": "name_of_person_commented",
    "comment_color": "comment_color",
    "is_client_comment": "is_client_comment",
    "comment_category": "comment_category",
    "is_handwritten": "is_handwritten",
    "extraction_confidence_percent": "extraction_confidence_percent",
}
DATETIME_SOURCE_FIELDS = ("date_of_comment", "time_of_comment")
DOCUMENT_SOURCE_FIELDS = ("praj_document_number", "praj_revision_number", "customer_document_number",
                          "customer_revision", "drawing_number_source", "revision_source",
                          "source_file_sha256", "source_file", "source_path")


def uid_source_suffix(uid: str) -> Optional[str]:
    """The 12-hex source-file suffix of a current-format comment_id, or None for legacy ids."""
    parts = str(uid).split("-")
    if len(parts) == 7 and _HEX12.match(parts[-1]):
        return parts[-1]
    return None


def read_extractor_csv(path) -> pd.DataFrame:
    """Read extractor output as TEXT; only truly empty cells become missing ('NA' stays 'NA')."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def _clean(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and v != v):
        return None
    v = str(v).strip()
    return v or None


def parse_comment_datetime(date_value, time_value) -> Optional[datetime]:
    """Exact formats only; None for anything missing, malformed or ambiguous."""
    d, t = _clean(date_value), _clean(time_value)
    if not d or not t or d.upper() == "NA" or t.upper() == "NA":
        return None
    m = _DMY.match(d)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = _YMD.match(d)
        if not m:
            return None
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    tm = _TIME.match(t)
    if not tm:
        return None
    try:
        return datetime(year, month, day, int(tm.group(1)), int(tm.group(2)), int(tm.group(3) or 0))
    except ValueError:
        return None


def _yes(v) -> bool:
    return (_clean(v) or "").upper() == "Y"


def _numeric(v) -> Optional[Decimal]:
    v = _clean(v)
    if v is None:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def map_comment_row(r: Dict) -> Dict:
    """One extractor row -> a dict keyed by db.COMMENT_INSERT_COLUMNS (allowlist only)."""
    return {
        "comment_id": _clean(r.get("comment_id")),
        "page_sheet": _clean(r.get("page_sheet")),
        "actual_extracted_comment": _clean(r.get("actual_extracted_comment")),
        "snapshot_file": _clean(r.get("snapshot_file")),
        "name_of_person_commented": _clean(r.get("name_of_person_commented")),
        "comment_datetime": parse_comment_datetime(r.get("date_of_comment"), r.get("time_of_comment")),
        "comment_color": _clean(r.get("comment_color")),
        "is_client_comment": _yes(r.get("is_client_comment")),
        "comment_category": _clean(r.get("comment_category")),
        "is_handwritten": _yes(r.get("is_handwritten")),
        "extraction_confidence_percent": _numeric(r.get("extraction_confidence_percent")),
    }


def dropped_columns(df: pd.DataFrame) -> List[str]:
    known = set(COMMENT_FIELD_MAP) | set(DATETIME_SOURCE_FIELDS) | set(DOCUMENT_SOURCE_FIELDS)
    return sorted(c for c in df.columns if c not in known)


def _first(group: pd.DataFrame, col: str) -> Optional[str]:
    if col not in group:
        return None
    vals = [v for v in group[col].tolist() if isinstance(v, str) and v.strip()]
    return vals[0] if vals else None


def _resolve_identity(group: pd.DataFrame, sha: Optional[str],
                      allow_unresolved: bool) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """-> (document number, revision, problem). problem is None when the group may be ingested."""
    if "praj_revision_number" in group and group["praj_revision_number"].fillna("").nunique() > 1:
        return None, None, "rows of one source file disagree on the revision"
    drawing = _first(group, "praj_document_number")
    revision = _first(group, "praj_revision_number") or db.MISSING_REVISION
    if "revision_source" in group and _first(group, "revision_source") == "unresolved":
        revision = db.MISSING_REVISION
    drawing_unresolved = (not drawing or drawing == "UNKNOWN"
                          or ("drawing_number_source" in group and _first(group, "drawing_number_source") == "unresolved"))
    if drawing_unresolved:
        if not allow_unresolved:
            return drawing, revision, "unresolved drawing number (use --allow-unresolved to ingest)"
        if not sha:
            return drawing, revision, "unresolved drawing number and no source_file_sha256 to isolate it"
        drawing = f"UNRESOLVED-{sha[:12].upper()}"
    return drawing, revision, None


def ingest_dataframe(df: pd.DataFrame, source_label: str, praj_project_number: str, supplier_name: str,
                     supplier_po_number: str, allow_unresolved: bool = False, embed: bool = True) -> dict:
    for name, value in (("project", praj_project_number), ("supplier", supplier_name), ("po", supplier_po_number)):
        if value is None or not str(value).strip():
            raise ValueError(f"--{name} is required (it comes from the upload form; it is never defaulted)")
    totals = {"groups": 0, "comments": 0, "already_present": 0, "rows_without_text": 0,
              "datetime_not_stored": 0, "embedded": 0, "embedding_failed": 0,
              "skipped": [], "conflicts": [], "documents": [], "dropped_columns": []}
    if df.empty:
        logger.info(f"{source_label}: no rows, skipping")
        return totals
    totals["dropped_columns"] = dropped_columns(df)
    if totals["dropped_columns"]:
        logger.info(f"{source_label}: columns not stored (no DB column): {', '.join(totals['dropped_columns'])}")

    df = df.copy()
    if "source_file_sha256" in df and df["source_file_sha256"].notna().all():
        keys = df["source_file_sha256"]
    else:
        logger.warning(f"{source_label}: no source_file_sha256 column; grouping by source_file / document "
                       f"number (re-extract to get exact source isolation)")
        keys = df["source_file"].fillna("") if "source_file" in df else \
            df.get("praj_document_number", pd.Series([""] * len(df))).fillna("")

    for key, group in df.groupby(keys, sort=True):
        totals["groups"] += 1
        sha = key if "source_file_sha256" in df and _HEX12.match(str(key)[:12].upper()) else None
        label = _first(group, "source_path") or _first(group, "source_file") or str(key)[:16]
        drawing, revision, problem = _resolve_identity(group, sha, allow_unresolved)
        if problem:
            logger.warning(f"SKIP {label}: {problem}")
            totals["skipped"].append({"source": label, "reason": problem})
            continue

        rows = []
        for r in group.to_dict("records"):
            m = map_comment_row(r)
            if not m["comment_id"] or not m["actual_extracted_comment"]:
                totals["rows_without_text"] += 1
                continue
            if m["comment_datetime"] is None and _clean(r.get("date_of_comment")) not in (None, "NA"):
                totals["datetime_not_stored"] += 1
            rows.append(m)
        key_desc = f"{praj_project_number}/{drawing}/{revision}/{supplier_name}/{supplier_po_number}"

        # Conflict 1: these comment_ids already belong to a different document row.
        existing_doc = db.find_document(praj_project_number, drawing, revision, supplier_name, supplier_po_number)
        owners = db.comment_id_owners([m["comment_id"] for m in rows])
        foreign = sorted({d for d in owners.values() if d != existing_doc})
        if foreign:
            msg = (f"this file's comments are already stored under another document row "
                   f"(document id {', '.join(map(str, foreign))}); comment_id is globally unique, so it "
                   f"cannot also be stored under {key_desc}")
            logger.error(f"CONFLICT {label}: {msg}")
            totals["conflicts"].append({"source": label, "reason": msg})
            continue
        # Conflict 2: the revision already holds comments from a different source file.
        if existing_doc is not None and sha:
            held = {uid_source_suffix(c) for c in db.get_comment_ids_for_document(existing_doc)}
            held.discard(None)
            if held and held != {sha[:12].upper()}:
                msg = (f"revision {key_desc} already holds comments from another source file "
                       f"({', '.join(sorted(held))}); not merged")
                logger.error(f"CONFLICT {label}: {msg}")
                totals["conflicts"].append({"source": label, "reason": msg})
                continue

        document_id = db.upsert_document(praj_project_number, drawing, revision, supplier_name, supplier_po_number,
                                         _first(group, "customer_document_number"), _first(group, "customer_revision"))
        inserted = db.insert_comments(document_id, rows)
        totals["comments"] += inserted
        totals["already_present"] += len(rows) - inserted
        totals["documents"].append({"source": label, "document_id": document_id, "key": key_desc,
                                    "inserted": inserted, "already_present": len(rows) - inserted})
        logger.info(f"{label} -> document {document_id} ({key_desc}): inserted {inserted}, "
                    f"already present {len(rows) - inserted}")

    if embed:
        result = comment_sync.sync_embeddings()
        totals["embedded"], totals["embedding_failed"] = result["embedded"], result["failed"]
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="final_output.csv or master_comments.csv")
    parser.add_argument("--project", required=True, help="praj_project_number (from the upload form)")
    parser.add_argument("--supplier", required=True, help="supplier_name (from the upload form)")
    parser.add_argument("--po", required=True, help="supplier_po_number (from the upload form)")
    parser.add_argument("--allow-unresolved", action="store_true",
                        help="ingest files with an unresolved drawing number as UNRESOLVED-<sha12>")
    parser.add_argument("--no-embed", action="store_true", help="store in Postgres only; embed later")
    args = parser.parse_args(argv)

    db.init_pool()
    df = read_extractor_csv(args.input)
    totals = ingest_dataframe(df, args.input, args.project, args.supplier, args.po,
                              allow_unresolved=args.allow_unresolved, embed=not args.no_embed)
    logger.info("=" * 50)
    logger.info(f"Ingestion complete | files={totals['groups']} inserted={totals['comments']} "
                f"already_present={totals['already_present']} embedded={totals['embedded']} "
                f"embedding_failed={totals['embedding_failed']} skipped={len(totals['skipped'])} "
                f"conflicts={len(totals['conflicts'])} datetime_not_stored={totals['datetime_not_stored']}")
    for s in totals["skipped"]:
        logger.info(f"  skipped  {s['source']}: {s['reason']}")
    for c in totals["conflicts"]:
        logger.info(f"  conflict {c['source']}: {c['reason']}")
    logger.info("=" * 50)
    return totals


if __name__ == "__main__":
    main()

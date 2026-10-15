"""
ingest.py

Bridges comment_extractor.py's real output (final_output.csv per PDF,
or master_comments.csv across all PDFs) into Postgres + Qdrant.

comment_extractor.py writes, per PDF: output/<pdf_stem>/final_output.csv
and, across all PDFs in one run: output/master_comments.csv

Usage:
    python ingest.py --input output/<pdf_stem>/final_output.csv
    python ingest.py --input output/master_comments.csv --all
"""
import re
import sys
import logging
import argparse
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from database import db
from vectordb import qdrant_client as vdb
from vectordb import embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def parse_uid(uid: str):
    """comment_id format: PROJECT-DRAWING-...-page-row-seq (project/drawing sanitized, no dashes)."""
    parts = str(uid).split("-")
    if len(parts) < 4:
        return parts[0] if parts else "UNKNOWN", "UNKNOWN"
    return parts[0], parts[1]


def ingest_dataframe(df: pd.DataFrame, source_label: str) -> dict:
    if df.empty:
        logger.info(f"{source_label}: no rows, skipping")
        return {"comments": 0, "embedded": 0}

    totals = {"comments": 0, "embedded": 0}

    # Group by (project, drawing, revision) so each PDF's comments land
    # under the correct document/revision, even inside a combined master CSV.
    df = df.copy()
    df["_project"], df["_drawing"] = zip(*df["comment_id"].map(parse_uid))
    group_cols = ["_project", "_drawing", "praj_revision_number"]

    for (project_code, drawing_number, revision), group in df.groupby(group_cols):
        project_id = db.get_or_create_project(project_code=project_code)
        document_id = db.get_or_create_document(project_id=project_id, drawing_number=drawing_number)
        revision_id = db.create_revision(
            document_id=document_id,
            praj_revision_number=str(revision) if pd.notna(revision) else "R0",
            customer_document_number=group["customer_document_number"].iloc[0] if "customer_document_number" in group else None,
            customer_revision=group["customer_revision"].iloc[0] if "customer_revision" in group else None,
        )

        records = group.to_dict("records")
        inserted = db.insert_comments_bulk(revision_id, records)
        totals["comments"] += inserted
        logger.info(f"{project_code}/{drawing_number}/{revision}: inserted {inserted} comments")

        # Embed + push to Qdrant
        db_comments = db.get_comments_by_revision(revision_id)
        embed_items = []
        for c in db_comments:
            if c["embedded"]:
                continue
            text = c["actual_extracted_comment"]
            try:
                vector = embedder.embed_text(text)
            except Exception as e:
                logger.warning(f"Embedding skipped for {c['id']}: {e}")
                continue
            embed_items.append({
                "comment_id": c["id"], "vector": vector, "text": text,
                "category": c["comment_category"], "project_id": project_id, "revision_id": revision_id,
            })
        if embed_items:
            vdb.upsert_comment_embeddings_bulk(embed_items)
            db.mark_comments_embedded([i["comment_id"] for i in embed_items])
            totals["embedded"] += len(embed_items)

    return totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="final_output.csv or master_comments.csv")
    args = parser.parse_args()

    db.init_pool()
    vdb.ensure_collections()
    if not embedder.check_ready():
        logger.warning("Ollama embedding model not ready — embeddings will be skipped. "
                        "Run: ollama pull nomic-embed-text")

    df = pd.read_csv(args.input)
    totals = ingest_dataframe(df, args.input)

    logger.info("=" * 50)
    logger.info(f"Ingestion complete | comments={totals['comments']} embedded={totals['embedded']}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()

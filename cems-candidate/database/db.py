"""
database/db.py

PostgreSQL access for the FINAL CEMS schema (database/schema.sql): exactly three tables,
documents / users / comments, bigint ids everywhere.

  * A document REVISION is one row in `documents`, unique on the constraint
    unique_doc_revision (praj_project_number, praj_document_number, praj_revision_number,
    supplier_name, supplier_po_number). praj_document_number alone is NOT unique.
  * comments.comment_id (the extractor's business key) is globally UNIQUE; ingest is
    idempotent through ON CONFLICT (comment_id).
  * comments.id (bigint) is the primary key and the Qdrant point id.
  * Status values used by the app: 'open' and 'closed' (plain varchar, no CHECK).
  * Users / login / roles are handled by the Express backend; nothing here touches them.
"""
import os
import logging
from contextlib import contextmanager
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)

_pool: Optional[SimpleConnectionPool] = None

STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
MISSING_REVISION = "NA"          # what the extractor emits for an unknown revision

# Exactly the comments columns ingest may write (the loader maps extractor fields onto these).
COMMENT_INSERT_COLUMNS = (
    "comment_id", "page_sheet", "actual_extracted_comment", "snapshot_file",
    "name_of_person_commented", "comment_datetime", "comment_color", "is_client_comment",
    "comment_category", "is_handwritten", "extraction_confidence_percent",
)


def init_pool(minconn: int = 1, maxconn: int = 10, **kwargs) -> None:
    global _pool
    _pool = SimpleConnectionPool(
        minconn, maxconn,
        host=kwargs.get("host") or os.getenv("POSTGRES_HOST", "localhost"),
        port=kwargs.get("port") or os.getenv("POSTGRES_PORT", "5432"),
        dbname=kwargs.get("dbname") or os.getenv("POSTGRES_DB", "cems"),
        user=kwargs.get("user") or os.getenv("POSTGRES_USER", "cems"),
        password=kwargs.get("password") or os.getenv("POSTGRES_PASSWORD", "cems_dev_password"),
    )
    logger.info("PostgreSQL connection pool initialized")


@contextmanager
def get_cursor(commit: bool = False):
    if _pool is None:
        init_pool()
    conn = _pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        _pool.putconn(conn)


def _na_to_null(v: Optional[str]) -> Optional[str]:
    """Customer document number / revision: the extractor writes 'NA' when unknown; the team's
    existing SQL stored that as NULL (NULLIF(..., 'NA')). Keep the same convention."""
    if v is None:
        return None
    v = str(v).strip()
    return None if v in ("", "NA") else v


# ============================
# DOCUMENTS (one row per revision)
# ============================

def find_document(praj_project_number: str, praj_document_number: str, praj_revision_number: Optional[str],
                  supplier_name: str, supplier_po_number: str) -> Optional[int]:
    rev = praj_revision_number or MISSING_REVISION
    with get_cursor() as cur:
        cur.execute(
            """SELECT id FROM documents
               WHERE praj_project_number = %s AND praj_document_number = %s AND praj_revision_number = %s
                 AND supplier_name = %s AND supplier_po_number = %s""",
            (praj_project_number, praj_document_number, rev, supplier_name, supplier_po_number))
        row = cur.fetchone()
        return row["id"] if row else None


def upsert_document(praj_project_number: str, praj_document_number: str, praj_revision_number: Optional[str],
                    supplier_name: str, supplier_po_number: str,
                    customer_document_number: Optional[str] = None,
                    customer_revision: Optional[str] = None) -> int:
    """Idempotent on unique_doc_revision. A missing revision is stored as 'NA' so that a
    re-ingest finds the same row (NULLs are distinct in a UNIQUE constraint). Customer fields
    are only filled when the existing row has none; they are never overwritten."""
    for name, value in (("praj_project_number", praj_project_number), ("praj_document_number", praj_document_number),
                        ("supplier_name", supplier_name), ("supplier_po_number", supplier_po_number)):
        if value is None or not str(value).strip():
            raise ValueError(f"{name} is required for a document row")
    rev = praj_revision_number or MISSING_REVISION
    with get_cursor(commit=True) as cur:
        cur.execute(
            """INSERT INTO documents (praj_project_number, praj_document_number, praj_revision_number,
                                      supplier_name, supplier_po_number,
                                      customer_document_number, customer_revision)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT ON CONSTRAINT unique_doc_revision DO UPDATE SET
                   customer_document_number = COALESCE(documents.customer_document_number,
                                                       EXCLUDED.customer_document_number),
                   customer_revision = COALESCE(documents.customer_revision, EXCLUDED.customer_revision)
               RETURNING id""",
            (praj_project_number, praj_document_number, rev, supplier_name, supplier_po_number,
             _na_to_null(customer_document_number), _na_to_null(customer_revision)))
        return cur.fetchone()["id"]


def get_document(document_id: int) -> Optional[Dict]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_document_revisions(praj_project_number: str, praj_document_number: str) -> List[Dict]:
    """All revisions of one drawing (several rows), newest first."""
    with get_cursor() as cur:
        cur.execute("""SELECT * FROM documents WHERE praj_project_number = %s AND praj_document_number = %s
                       ORDER BY created_at DESC, id DESC""", (praj_project_number, praj_document_number))
        return [dict(r) for r in cur.fetchall()]


# ============================
# COMMENTS
# ============================

def comment_id_owners(comment_ids: List[str]) -> Dict[str, int]:
    """comment_id -> document_id for the given business keys that already exist."""
    if not comment_ids:
        return {}
    with get_cursor() as cur:
        cur.execute("SELECT comment_id, document_id FROM comments WHERE comment_id = ANY(%s)", (list(comment_ids),))
        return {r["comment_id"]: r["document_id"] for r in cur.fetchall()}


def get_comment_ids_for_document(document_id: int) -> List[str]:
    with get_cursor() as cur:
        cur.execute("SELECT comment_id FROM comments WHERE document_id = %s", (document_id,))
        return [r["comment_id"] for r in cur.fetchall()]


def insert_comments(document_id: int, rows: List[Dict]) -> int:
    """rows: dicts keyed by COMMENT_INSERT_COLUMNS (already mapped by the loader).
    Idempotent: ON CONFLICT (comment_id) DO NOTHING. New rows start embedded=false.
    Returns the number of rows actually inserted (counted with SELECTs, not rowcount)."""
    if not rows:
        return 0
    values = [(document_id,) + tuple(r.get(c) for c in COMMENT_INSERT_COLUMNS) for r in rows]
    cols = ", ".join(("document_id",) + COMMENT_INSERT_COLUMNS)
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT count(*) AS n FROM comments WHERE document_id = %s", (document_id,))
        before = cur.fetchone()["n"]
        psycopg2.extras.execute_values(
            cur, f"INSERT INTO comments ({cols}) VALUES %s ON CONFLICT (comment_id) DO NOTHING", values)
        cur.execute("SELECT count(*) AS n FROM comments WHERE document_id = %s", (document_id,))
        return cur.fetchone()["n"] - before


_COMMENT_WITH_DOCUMENT = """
    SELECT c.id, c.comment_id, c.document_id, c.page_sheet, c.actual_extracted_comment,
           c.snapshot_file, c.name_of_person_commented, c.comment_datetime, c.comment_color,
           c.is_client_comment, c.comment_category, c.is_handwritten, c.extraction_confidence_percent,
           c.created_at, c.assigned_to, c.target_closure_date, c.status, c.embedded,
           c.ai_suggested_resolution, c.ai_confidence_percent, c.resolution_text, c.resolved_at,
           d.praj_project_number, d.praj_document_number, d.praj_revision_number,
           d.supplier_name, d.supplier_po_number, d.customer_document_number, d.customer_revision,
           d.is_released
    FROM comments c JOIN documents d ON d.id = c.document_id
"""


def get_comment_context(comment_id: int) -> Optional[Dict]:
    """One comment with its document (revision) fields; reads only comments JOIN documents."""
    with get_cursor() as cur:
        cur.execute(_COMMENT_WITH_DOCUMENT + " WHERE c.id = %s", (comment_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_comments_to_embed(limit: int = 500, ids: Optional[List[int]] = None) -> List[Dict]:
    """Comments with embedded = false (or exactly `ids`), with the fields the Qdrant payload needs."""
    with get_cursor() as cur:
        if ids:
            cur.execute(_COMMENT_WITH_DOCUMENT + " WHERE c.id = ANY(%s::bigint[]) ORDER BY c.id", (list(ids),))
        else:
            cur.execute(_COMMENT_WITH_DOCUMENT + " WHERE c.embedded = false ORDER BY c.id LIMIT %s", (limit,))
        return [dict(r) for r in cur.fetchall()]


def mark_comments_embedded(ids: List[int], embedded: bool = True) -> None:
    if not ids:
        return
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE comments SET embedded = %s WHERE id = ANY(%s::bigint[])", (embedded, list(ids)))


def reset_all_embedded() -> int:
    """Every comment back to embedded = false (used when the Qdrant collection is rebuilt)."""
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE comments SET embedded = false WHERE embedded = true")
        return cur.rowcount


def save_ai_suggestion(comment_id: int, suggestion: str, confidence: Optional[float]) -> bool:
    """Store the AI DRAFT. Never touches resolution_text, resolved_at or status."""
    with get_cursor(commit=True) as cur:
        cur.execute("""UPDATE comments SET ai_suggested_resolution = %s, ai_confidence_percent = %s
                       WHERE id = %s RETURNING id""", (suggestion, confidence, comment_id))
        return cur.fetchone() is not None


def resolve_comment(comment_id: int, resolution_text: str) -> Optional[Dict]:
    """Human approval: store the approved (possibly edited) text, set status 'closed' and
    resolved_at = now. Returns the updated comment with its document, or None if not found."""
    if resolution_text is None or not str(resolution_text).strip():
        raise ValueError("resolution_text must not be empty")
    with get_cursor(commit=True) as cur:
        cur.execute("""UPDATE comments SET resolution_text = %s, resolved_at = CURRENT_TIMESTAMP, status = %s
                       WHERE id = %s RETURNING id""", (resolution_text.strip(), STATUS_CLOSED, comment_id))
        if cur.fetchone() is None:
            return None
    return get_comment_context(comment_id)


def reopen_comment(comment_id: int) -> Optional[Dict]:
    """Status back to 'open' and resolved_at cleared. resolution_text is kept as history."""
    with get_cursor(commit=True) as cur:
        cur.execute("""UPDATE comments SET status = %s, resolved_at = NULL WHERE id = %s RETURNING id""",
                    (STATUS_OPEN, comment_id))
        if cur.fetchone() is None:
            return None
    return get_comment_context(comment_id)

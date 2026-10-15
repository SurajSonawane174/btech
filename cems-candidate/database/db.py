"""
database/db.py

PostgreSQL connection layer. Field names match comment_extractor.py's
real COLUMNS list exactly (verified against the source, not assumed).
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


# ============================
# RBAC
# ============================

def get_or_create_user(email: str, display_name: str = None) -> str:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO users (email, display_name) VALUES (%s, %s)
            ON CONFLICT (email) DO UPDATE
                SET display_name = COALESCE(EXCLUDED.display_name, users.display_name)
            RETURNING id
            """,
            (email, display_name),
        )
        return str(cur.fetchone()["id"])


def set_project_role(user_id: str, project_id: str, role: str) -> None:
    assert role in ("admin", "reviewer", "viewer"), f"invalid role: {role}"
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO project_memberships (user_id, project_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, project_id) DO UPDATE SET role = EXCLUDED.role
            """,
            (user_id, project_id, role),
        )


def get_user_role(user_id: str, project_id: str) -> Optional[str]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT role FROM project_memberships WHERE user_id=%s AND project_id=%s",
            (user_id, project_id),
        )
        row = cur.fetchone()
        return row["role"] if row else None


# Permission matrix — the actual RBAC enforcement point.
# Checked in application code before any mutating action.
PERMISSIONS = {
    "view_comments":        {"admin", "reviewer", "viewer"},
    "override_classification": {"admin", "reviewer"},
    "assign_comment":       {"admin", "reviewer"},
    "resolve_comment":      {"admin", "reviewer"},
    "delete_comment":       {"admin"},
    "manage_members":       {"admin"},
}


def can(user_id: str, project_id: str, action: str) -> bool:
    role = get_user_role(user_id, project_id)
    if role is None:
        return False
    allowed_roles = PERMISSIONS.get(action)
    if allowed_roles is None:
        raise ValueError(f"unknown permission action: {action}")
    return role in allowed_roles


# ============================
# PROJECTS / DOCUMENTS / REVISIONS
# ============================

def get_or_create_project(project_code: str, project_name: str = None, client_name: str = None) -> str:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO projects (project_code, project_name, client_name)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_code) DO UPDATE
                SET project_name = COALESCE(EXCLUDED.project_name, projects.project_name)
            RETURNING id
            """,
            (project_code, project_name, client_name),
        )
        return str(cur.fetchone()["id"])


def get_or_create_document(project_id: str, drawing_number: str, document_title: str = None) -> str:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO documents (project_id, drawing_number, document_title)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id, drawing_number) DO UPDATE
                SET document_title = COALESCE(EXCLUDED.document_title, documents.document_title)
            RETURNING id
            """,
            (project_id, drawing_number, document_title),
        )
        return str(cur.fetchone()["id"])


def create_revision(document_id: str, praj_revision_number: str,
                     customer_document_number: str = None, customer_revision: str = None,
                     source_pdf_path: str = None) -> str:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO revisions
                (document_id, praj_revision_number, customer_document_number,
                 customer_revision, source_pdf_path)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (document_id, praj_revision_number) DO UPDATE
                SET source_pdf_path = EXCLUDED.source_pdf_path, processed_at = now()
            RETURNING id
            """,
            (document_id, praj_revision_number, customer_document_number,
             customer_revision, source_pdf_path),
        )
        return str(cur.fetchone()["id"])


# ============================
# COMMENTS — field names match comment_extractor.py's COLUMNS exactly
# ============================

def insert_comments_bulk(revision_id: str, records: List[Dict]) -> int:
    """
    records: rows from master_comments.csv / final_output.csv, using
    comment_extractor.py's exact column names:
      sr_no, comment_id, page_sheet, actual_extracted_comment,
      snapshot_file, name_of_person_commented, email_of_person_commented,
      date_of_comment, time_of_comment, comment_color, is_client_comment,
      comment_category, is_handwritten, extraction_confidence_percent,
      annotation_type, classification_method, comment_source
    """
    if not records:
        return 0

    rows = []
    for r in records:
        rows.append((
            revision_id,
            r.get("sr_no"),
            r.get("comment_id"),
            r.get("page_sheet"),
            r.get("actual_extracted_comment"),
            r.get("snapshot_file"),
            r.get("name_of_person_commented"),
            r.get("email_of_person_commented"),
            r.get("date_of_comment"),
            r.get("time_of_comment"),
            r.get("comment_color"),
            str(r.get("is_client_comment")).upper() == "Y",
            _normalize_category(r.get("comment_category")),
            str(r.get("is_handwritten")).upper() == "Y",
            r.get("extraction_confidence_percent"),
            r.get("annotation_type"),
            r.get("classification_method"),
            r.get("comment_source"),
            _none_if_nan(r.get("visual_feature")),
        ))

    with get_cursor(commit=True) as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO comments (
                revision_id, sr_no, comment_uid, page_sheet,
                actual_extracted_comment, snapshot_file,
                name_of_person_commented, email_of_person_commented,
                date_of_comment, time_of_comment, comment_color,
                is_client_comment, comment_category, is_handwritten,
                extraction_confidence_percent, annotation_type,
                classification_method, comment_source, visual_feature
            ) VALUES %s
            ON CONFLICT (revision_id, comment_uid) DO NOTHING
            """,
            rows,
        )
        cur.execute("UPDATE revisions SET total_comments = %s WHERE id = %s",
                    (len(records), revision_id))
        return cur.rowcount


def _none_if_nan(v):
    """pandas reads empty CSV cells as float NaN; store them as NULL, not the string 'nan'."""
    if v is None or (isinstance(v, float) and v != v) or (isinstance(v, str) and not v.strip()):
        return None
    return v


def _normalize_category(cat: Optional[str]) -> str:
    valid = {"technical", "aesthetic", "repeated", "uncategorized"}
    if cat and str(cat).lower() in valid:
        return str(cat).lower()
    return "uncategorized"


def get_comments_by_revision(revision_id: str) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, comment_uid, actual_extracted_comment, comment_category,
                   classification_method, comment_source, embedded
            FROM comments WHERE revision_id = %s
            """,
            (revision_id,),
        )
        return [dict(row) for row in cur.fetchall()]


def mark_comments_embedded(comment_ids: List[str]) -> None:
    if not comment_ids:
        return

    with get_cursor(commit=True) as cur:
        cur.execute(
            "UPDATE comments SET embedded = true WHERE id = ANY(%s::uuid[])",
            (comment_ids,),
        )


def get_resolution_history_for(comment_ids: List[str]) -> List[Dict]:
    if not comment_ids:
        return []
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT c.id AS comment_id, c.actual_extracted_comment,
                   r.resolution_text, r.resolved_by, r.resolved_at
            FROM comments c
            JOIN resolutions r ON r.comment_id = c.id
            WHERE c.id = ANY(%s::uuid[])
            ORDER BY r.resolved_at DESC
            """,
            (comment_ids,),
        )
        return [dict(row) for row in cur.fetchall()]


def insert_resolution(comment_id: str, resolution_text: str, resolved_by: str = None,
                       source: str = "manual", ai_recommendation_text: str = None,
                       ai_confidence_percent: int = None, ai_cited_standards: List[str] = None,
                       ai_similar_comment_ids: List[str] = None) -> str:
    with get_cursor(commit=True) as cur:
        cur.execute(    
            """
            INSERT INTO resolutions (
                comment_id, resolution_text, resolved_by, source,
                ai_recommendation_text, ai_confidence_percent,
                ai_cited_standards, ai_similar_comment_ids
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (comment_id, resolution_text, resolved_by, source, ai_recommendation_text,
            ai_confidence_percent, ai_cited_standards, ai_similar_comment_ids),
        )

        resolution_id = str(cur.fetchone()["id"])

        cur.execute(
            "UPDATE comments SET status = 'resolved' WHERE id = %s",
            (comment_id,),
        )

        return resolution_id


# ============================
# ENTITIES / GRAPH EDGES (Stage 4)
# ============================

def get_or_create_entity(entity_type: str, entity_value: str, project_id: str) -> str:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO entities (entity_type, entity_value, project_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (project_id, entity_type, entity_value) DO UPDATE
                SET entity_type = EXCLUDED.entity_type
            RETURNING id
            """,
            (entity_type, entity_value, project_id),
        )
        return str(cur.fetchone()["id"])


def link_comment_entity(comment_id: str, entity_id: str, confidence: int = None) -> None:
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO comment_entity_edges (comment_id, entity_id, confidence)
            VALUES (%s, %s, %s) ON CONFLICT (comment_id, entity_id) DO NOTHING
            """,
            (comment_id, entity_id, confidence),
        )


def get_comments_for_entity(entity_type: str, entity_value: str, project_id: str) -> List[Dict]:
    """Graph traversal: 'show me all comments touching Pump P-102'."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT c.comment_uid, c.actual_extracted_comment, c.comment_category, c.status
            FROM comments c
            JOIN comment_entity_edges e ON e.comment_id = c.id
            JOIN entities en ON en.id = e.entity_id
            WHERE en.entity_type = %s AND en.entity_value = %s AND en.project_id = %s
            """,
            (entity_type, entity_value, project_id),
        )
        return [dict(row) for row in cur.fetchall()]


# ============================
# STANDARDS CORPUS
# ============================

def get_or_create_standards_document(title: str, code_reference: str, discipline: str = None) -> str:
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM standards_documents WHERE code_reference = %s", (code_reference,))
        existing = cur.fetchone()
        if existing:
            return str(existing["id"])
        cur.execute(
            """
            INSERT INTO standards_documents (title, code_reference, discipline)
            VALUES (%s, %s, %s) RETURNING id
            """,
            (title, code_reference, discipline),
        )
        return str(cur.fetchone()["id"])


def insert_standards_chunks_bulk(document_id: str, chunks: List[Dict]) -> int:
    if not chunks:
        return 0
    rows = [(document_id, c["chunk_index"], c["chunk_text"], c.get("page_number"),
              c.get("section_reference")) for c in chunks]
    with get_cursor(commit=True) as cur:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO standards_chunks
                (standards_document_id, chunk_index, chunk_text, page_number, section_reference)
            VALUES %s
            """,
            rows,
        )
        return cur.rowcount


def get_unembedded_standards_chunks(limit: int = 500) -> List[Dict]:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT sc.id, sc.chunk_text, sc.section_reference, sd.code_reference, sd.title
            FROM standards_chunks sc
            JOIN standards_documents sd ON sd.id = sc.standards_document_id
            WHERE sc.embedded = false LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def mark_standards_chunks_embedded(chunk_ids: List[str]) -> None:
    if not chunk_ids:
        return
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE standards_chunks SET embedded = true WHERE id = ANY(%s::uuid[])", (chunk_ids,))


# ============================
# AGENTIC RAG TRACE LOG
# ============================

def log_rag_trace(comment_id: Optional[str], original_query: str, decomposed_subqueries: List[str],
                   retrieval_hops: list, faithfulness_passed: bool, faithfulness_notes: str,
                   final_answer: str, cited_chunk_ids: List[str]) -> str:
    import json
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO rag_query_traces (
                comment_id, original_query, decomposed_subqueries, retrieval_hops,
                faithfulness_passed, faithfulness_notes, final_answer, cited_chunk_ids
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (comment_id, original_query, decomposed_subqueries, json.dumps(retrieval_hops),
             faithfulness_passed, faithfulness_notes, final_answer, cited_chunk_ids),
        )
        return str(cur.fetchone()["id"])

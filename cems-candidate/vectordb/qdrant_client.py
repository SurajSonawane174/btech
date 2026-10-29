"""
vectordb/qdrant_client.py

Qdrant holds every vector and all RAG text; Postgres holds the operational records.

  "comments"          point id = comments.id (positive bigint, no UUID)
                      vector   = embedding of actual_extracted_comment
                      payload  = comment_id, document_id, praj_project_number, praj_document_number,
                                 praj_revision_number, comment_category, is_client_comment, status,
                                 text (the comment, for display), resolution_text (when closed)
  "standards_chunks"  point id = stable positive integer generated at seeding
                      payload  = code_reference, section_reference, page_number, chunk_text,
                                 title, corpus_status ('illustrative_placeholder' until real
                                 PRAJ-approved standards are loaded)

Collection names can be overridden (QDRANT_COMMENTS_COLLECTION / QDRANT_STANDARDS_COLLECTION) so a
demo or test can use its own collections and never touch the team's.
"""
import os
import logging
from typing import Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

# Overridable so a demo or smoke test can use its own collections and never touch the team's.
COMMENTS_COLLECTION  = os.getenv("QDRANT_COMMENTS_COLLECTION", "comments")
STANDARDS_COLLECTION = os.getenv("QDRANT_STANDARDS_COLLECTION", "standards_chunks")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
STATUS_CLOSED = "closed"

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
    return _client


def _create(name: str) -> None:
    get_client().create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(size=EMBEDDING_DIM, distance=qmodels.Distance.COSINE),
    )
    logger.info(f"Created Qdrant collection: {name}")


def ensure_collections() -> None:
    existing = {c.name for c in get_client().get_collections().collections}
    for name in (COMMENTS_COLLECTION, STANDARDS_COLLECTION):
        if name not in existing:
            _create(name)


def recreate_collection(name: str) -> None:
    """DESTRUCTIVE: drop and recreate one collection (used once, to move to integer point ids)."""
    if name not in (COMMENTS_COLLECTION, STANDARDS_COLLECTION):
        raise ValueError(f"refusing to recreate unknown collection {name!r}")
    client = get_client()
    if name in {c.name for c in client.get_collections().collections}:
        client.delete_collection(name)
    _create(name)


def _point_id(value) -> int:
    pid = int(value)
    if pid <= 0:
        raise ValueError(f"Qdrant point id must be a positive integer, got {value!r}")
    return pid


# ============================
# COMMENTS
# ============================

def comment_payload(row: Dict) -> Dict:
    """Payload for one comment row (db.get_comments_to_embed / get_comment_context shape)."""
    payload = {
        "comment_id": row.get("comment_id"), "document_id": row.get("document_id"),
        "praj_project_number": row.get("praj_project_number"),
        "praj_document_number": row.get("praj_document_number"),
        "praj_revision_number": row.get("praj_revision_number"),
        "comment_category": row.get("comment_category"),
        "is_client_comment": bool(row.get("is_client_comment")),
        "status": row.get("status"), "text": row.get("actual_extracted_comment"),
    }
    if row.get("status") == STATUS_CLOSED and row.get("resolution_text"):
        payload["resolution_text"] = row["resolution_text"]
    return payload


def upsert_comment_points(items: List[Dict]) -> None:
    """items: {id (comments.id), vector, payload}"""
    if not items:
        return
    points = [qmodels.PointStruct(id=_point_id(i["id"]), vector=i["vector"], payload=i["payload"]) for i in items]
    get_client().upsert(collection_name=COMMENTS_COLLECTION, points=points, wait=True)


def update_comment_payload(comment_pk: int, payload: Dict, remove_keys: Optional[List[str]] = None) -> None:
    """Change payload fields of an existing point (e.g. status + resolution_text on resolve)."""
    client = get_client()
    pid = _point_id(comment_pk)
    client.set_payload(collection_name=COMMENTS_COLLECTION, payload=payload, points=[pid], wait=True)
    if remove_keys:
        client.delete_payload(collection_name=COMMENTS_COLLECTION, keys=list(remove_keys), points=[pid], wait=True)


def search_similar_comments(query_vector: List[float], top_k: int = 5, score_threshold: float = 0.55,
                            praj_project_number: Optional[str] = None, comment_category: Optional[str] = None,
                            only_resolved: bool = False, exclude_ids: Optional[List[int]] = None,
                            exclude_document_id: Optional[int] = None) -> List[Dict]:
    """
    Nearest comments. Filters and exclusions are applied INSIDE Qdrant (so top_k is filled with
    eligible comments) and re-checked here:
      praj_project_number / comment_category   payload filters
      only_resolved                            status 'closed' (comments with an approved resolution)
      exclude_ids                              e.g. the query comment itself (comments.id)
      exclude_document_id                      e.g. the query comment's own revision row
    """
    must, must_not = [], []
    if praj_project_number:
        must.append(qmodels.FieldCondition(key="praj_project_number",
                                           match=qmodels.MatchValue(value=praj_project_number)))
    if comment_category:
        must.append(qmodels.FieldCondition(key="comment_category", match=qmodels.MatchValue(value=comment_category)))
    if only_resolved:
        must.append(qmodels.FieldCondition(key="status", match=qmodels.MatchValue(value=STATUS_CLOSED)))
    excluded = {_point_id(i) for i in (exclude_ids or []) if i}
    if excluded:
        must_not.append(qmodels.HasIdCondition(has_id=sorted(excluded)))
    if exclude_document_id is not None:
        must_not.append(qmodels.FieldCondition(key="document_id",
                                               match=qmodels.MatchValue(value=int(exclude_document_id))))
    query_filter = qmodels.Filter(must=must or None, must_not=must_not or None) if (must or must_not) else None

    response = get_client().query_points(
        collection_name=COMMENTS_COLLECTION, query=query_vector, query_filter=query_filter,
        limit=top_k, score_threshold=score_threshold, with_payload=True)
    out = []
    for r in response.points:
        p = r.payload or {}
        if int(r.id) in excluded or (exclude_document_id is not None and p.get("document_id") == exclude_document_id):
            continue
        if only_resolved and (p.get("status") != STATUS_CLOSED or not p.get("resolution_text")):
            continue
        out.append({"id": int(r.id), "score": r.score, "text": p.get("text"),
                    "comment_id": p.get("comment_id"), "document_id": p.get("document_id"),
                    "praj_project_number": p.get("praj_project_number"),
                    "praj_document_number": p.get("praj_document_number"),
                    "praj_revision_number": p.get("praj_revision_number"),
                    "comment_category": p.get("comment_category"), "status": p.get("status"),
                    "resolution_text": p.get("resolution_text")})
    return out


# ============================
# STANDARDS CHUNKS (agentic RAG)
# ============================

def upsert_standards_points(items: List[Dict]) -> None:
    """items: {id (int), vector, payload: {code_reference, section_reference, page_number, chunk_text, ...}}"""
    if not items:
        return
    points = [qmodels.PointStruct(id=_point_id(i["id"]), vector=i["vector"], payload=i["payload"]) for i in items]
    get_client().upsert(collection_name=STANDARDS_COLLECTION, points=points, wait=True)


def search_standards(query_vector: List[float], top_k: int = 5, code_reference: Optional[str] = None,
                     score_threshold: float = 0.45) -> List[Dict]:
    query_filter = None
    if code_reference:
        query_filter = qmodels.Filter(must=[qmodels.FieldCondition(
            key="code_reference", match=qmodels.MatchValue(value=code_reference))])
    response = get_client().query_points(
        collection_name=STANDARDS_COLLECTION, query=query_vector, query_filter=query_filter,
        limit=top_k, score_threshold=score_threshold, with_payload=True)
    return [{"chunk_id": int(r.id), "score": r.score, "text": (r.payload or {}).get("chunk_text"),
             "code_reference": (r.payload or {}).get("code_reference"),
             "section_reference": (r.payload or {}).get("section_reference"),
             "page_number": (r.payload or {}).get("page_number"),
             "title": (r.payload or {}).get("title"),
             "corpus_status": (r.payload or {}).get("corpus_status", "unknown")} for r in response.points]

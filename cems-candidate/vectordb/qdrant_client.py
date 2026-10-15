"""
vectordb/qdrant_client.py

Two collections:
  "comments"          — embeddings of extracted comments (Stage 1: similarity search)
  "standards_chunks"  — embeddings of chunked engineering standards (Stage 2: agentic RAG)
"""
import os
import logging
from typing import Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

COMMENTS_COLLECTION  = "comments"
STANDARDS_COLLECTION = "standards_chunks"
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
        )
    return _client


def ensure_collections() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    for name in (COMMENTS_COLLECTION, STANDARDS_COLLECTION):
        if name in existing:
            continue
        client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(size=EMBEDDING_DIM, distance=qmodels.Distance.COSINE),
        )
        logger.info(f"Created Qdrant collection: {name}")


# ============================
# COMMENTS (Stage 1)
# ============================

def upsert_comment_embeddings_bulk(items: List[Dict]) -> None:
    """items: {comment_id, vector, text, category, project_id, revision_id[, document_id, comment_uid]}
    document_id / comment_uid are provenance for retrieval results (absent on older points)."""
    if not items:
        return
    client = get_client()
    points = [
        qmodels.PointStruct(
            id=item["comment_id"], vector=item["vector"],
            payload={
                "text": item["text"], "comment_category": item.get("category"),
                "project_id": item.get("project_id"), "revision_id": item.get("revision_id"),
                "document_id": item.get("document_id"), "comment_uid": item.get("comment_uid"),
            },
        ) for item in items
    ]
    client.upsert(collection_name=COMMENTS_COLLECTION, points=points)


def search_similar_comments(query_vector: List[float], top_k: int = 5,
                             project_id: Optional[str] = None,
                             score_threshold: float = 0.55,
                             exclude_ids: Optional[List[str]] = None,
                             exclude_revision_id: Optional[str] = None) -> List[Dict]:
    """
    Nearest past comments. Exclusions are applied INSIDE Qdrant (so top_k is filled with other
    comments, not consumed by the excluded ones) and re-checked here:
      exclude_ids          the query comment itself (Qdrant point id == Postgres comments.id)
      exclude_revision_id  the query comment's own revision / source file, so "historical"
                           matches come from other reviews
    project_id restricts results to one project (client data isolation).
    """
    client = get_client()
    conditions, exclusions = [], []
    if project_id:
        conditions.append(qmodels.FieldCondition(
            key="project_id", match=qmodels.MatchValue(value=project_id)))
    excluded = {str(i) for i in (exclude_ids or []) if i}
    if excluded:
        exclusions.append(qmodels.HasIdCondition(has_id=sorted(excluded)))
    if exclude_revision_id:
        exclusions.append(qmodels.FieldCondition(
            key="revision_id", match=qmodels.MatchValue(value=exclude_revision_id)))
    query_filter = qmodels.Filter(must=conditions or None, must_not=exclusions or None) \
        if (conditions or exclusions) else None

    response = client.query_points(
        collection_name=COMMENTS_COLLECTION, query=query_vector,
        query_filter=query_filter, limit=top_k,
        score_threshold=score_threshold, with_payload=True,
    )
    out = []
    for r in response.points:
        payload = r.payload or {}
        if str(r.id) in excluded or (exclude_revision_id and payload.get("revision_id") == exclude_revision_id):
            continue
        out.append({"comment_id": str(r.id), "score": r.score, "text": payload.get("text"),
                    "category": payload.get("comment_category"), "project_id": payload.get("project_id"),
                    "revision_id": payload.get("revision_id"), "document_id": payload.get("document_id"),
                    "comment_uid": payload.get("comment_uid")})
    return out


# ============================
# STANDARDS CHUNKS (Stage 2 — agentic RAG)
# ============================

def upsert_standards_chunk_embeddings_bulk(items: List[Dict]) -> None:
    """items: {chunk_id, vector, text, code_reference, section_reference, title}"""
    if not items:
        return
    client = get_client()
    points = [
        qmodels.PointStruct(
            id=item["chunk_id"], vector=item["vector"],
            payload={
                "text": item["text"], "code_reference": item.get("code_reference"),
                "section_reference": item.get("section_reference"), "title": item.get("title"),
                "corpus_status": item.get("corpus_status", "unknown"),
            },
        ) for item in items
    ]
    client.upsert(collection_name=STANDARDS_COLLECTION, points=points)


def search_standards(query_vector: List[float], top_k: int = 5,
                      code_reference: Optional[str] = None,
                      score_threshold: float = 0.45) -> List[Dict]:
    client = get_client()
    query_filter = None
    if code_reference:
        query_filter = qmodels.Filter(must=[qmodels.FieldCondition(
            key="code_reference", match=qmodels.MatchValue(value=code_reference))])

    response = client.query_points(
        collection_name=STANDARDS_COLLECTION, query=query_vector,
        query_filter=query_filter, limit=top_k,
        score_threshold=score_threshold, with_payload=True,
    )
    return [{"chunk_id": str(r.id), "score": r.score, "text": r.payload.get("text"),
             "code_reference": r.payload.get("code_reference"),
             "section_reference": r.payload.get("section_reference"),
             "title": r.payload.get("title"),
             "corpus_status": r.payload.get("corpus_status", "unknown")} for r in response.points]

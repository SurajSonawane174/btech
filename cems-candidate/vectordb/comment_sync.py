"""
vectordb/comment_sync.py -- keep Qdrant in step with the `comments` table.

  sync_embeddings()      embed comments with embedded = false, upsert them (point id = comments.id),
                         then set embedded = true. Failures stay embedded = false and are retried
                         on the next run.
  resolve_comment()      human approval: DB first (resolution_text, resolved_at, status 'closed'),
                         then the Qdrant payload, so approved resolutions can be reused.
  reopen_comment()       status back to 'open', resolved_at cleared, payload updated.
  find_similar()         similar-comment search by text or by an existing comment's id.
  rebuild_comment_vectors()  DESTRUCTIVE one-off: recreate the collection with integer ids and
                         re-embed everything from Postgres.

If a Qdrant payload update fails after the database changed, the row is set back to
embedded = false so the next sync rewrites the point with the current status.
"""
import logging
from typing import Dict, List, Optional

from database import db
from vectordb import embedder
from vectordb import qdrant_client as vdb

logger = logging.getLogger(__name__)


def sync_embeddings(ids: Optional[List[int]] = None, batch_size: int = 200) -> Dict:
    """-> {"embedded": n, "failed": n, "failed_ids": [...]}"""
    vdb.ensure_collections()
    done, failed_ids = 0, []
    while True:
        rows = db.get_comments_to_embed(limit=batch_size + len(failed_ids), ids=ids)
        rows = [r for r in rows if r["id"] not in failed_ids]
        if not rows:
            break
        items = []
        for r in rows:
            try:
                items.append({"id": r["id"], "vector": embedder.embed_text(r["actual_extracted_comment"]),
                              "payload": vdb.comment_payload(r)})
            except Exception as e:
                logger.warning(f"embedding failed for comment {r['id']}: {e}")
                failed_ids.append(r["id"])
        if items:
            try:
                vdb.upsert_comment_points(items)
                db.mark_comments_embedded([i["id"] for i in items])
                done += len(items)
            except Exception as e:
                logger.error(f"Qdrant upsert failed ({e}); {len(items)} comment(s) stay embedded=false")
                failed_ids.extend(i["id"] for i in items)
        if ids is not None or not items:
            break
    return {"embedded": done, "failed": len(failed_ids), "failed_ids": failed_ids}


def _push_payload(row: Dict, remove_keys=None) -> Optional[str]:
    """Update the point's payload; on failure mark the row for re-sync. Returns a warning or None."""
    if not row.get("embedded"):
        return None                       # not in Qdrant yet: the next sync writes the full payload
    try:
        vdb.update_comment_payload(row["id"], vdb.comment_payload(row), remove_keys=remove_keys)
        return None
    except Exception as e:
        db.mark_comments_embedded([row["id"]], embedded=False)
        return f"Qdrant payload not updated ({type(e).__name__}); comment marked for re-sync"


def resolve_comment(comment_pk: int, resolution_text: str) -> Dict:
    row = db.resolve_comment(comment_pk, resolution_text)
    if row is None:
        raise LookupError(f"comment {comment_pk} not found")
    warning = _push_payload(row)
    return {"comment": row, "warning": warning}


def reopen_comment(comment_pk: int) -> Dict:
    row = db.reopen_comment(comment_pk)
    if row is None:
        raise LookupError(f"comment {comment_pk} not found")
    warning = _push_payload(row, remove_keys=["resolution_text"])
    return {"comment": row, "warning": warning}


def find_similar(text: Optional[str] = None, comment_pk: Optional[int] = None, top_k: int = 5,
                 score_threshold: float = 0.55, praj_project_number: Optional[str] = None,
                 comment_category: Optional[str] = None, only_resolved: bool = False) -> Dict:
    """Search by free text, or by an existing comment (its own text; itself excluded)."""
    exclude = []
    if comment_pk is not None:
        row = db.get_comment_context(comment_pk)
        if row is None:
            raise LookupError(f"comment {comment_pk} not found")
        text = row["actual_extracted_comment"]
        exclude = [comment_pk]
    if not text or not str(text).strip():
        raise ValueError("give a query text or a comment id")
    hits = vdb.search_similar_comments(embedder.embed_text(text), top_k=top_k, score_threshold=score_threshold,
                                       praj_project_number=praj_project_number, comment_category=comment_category,
                                       only_resolved=only_resolved, exclude_ids=exclude)
    return {"query": text, "results": hits}


def rebuild_comment_vectors() -> Dict:
    """DESTRUCTIVE: recreate the comments collection and re-embed every comment."""
    vdb.recreate_collection(vdb.COMMENTS_COLLECTION)
    reset = db.reset_all_embedded()
    result = sync_embeddings()
    return {"collection": vdb.COMMENTS_COLLECTION, "reset_rows": reset, **result}

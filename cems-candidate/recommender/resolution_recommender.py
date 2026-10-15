"""
recommender/resolution_recommender.py

Given a new comment, combines:
  1. Semantically similar past comments + how they were resolved (Stage 1)
  2. Grounded standards context, if the comment references a checkable
     requirement, with a faithfulness-passed guarantee (Stage 2)
into a single drafted resolution for the reviewer to approve/edit —
never auto-applied, always attributed as "AI-suggested" with its
sources, so a reviewer can verify before accepting.

Usage:
    from recommender.resolution_recommender import recommend_resolution
    result = recommend_resolution(comment_text, llm_client, project_id=...)
"""
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database import db
from vectordb import qdrant_client as vdb
from vectordb import embedder
from agentic_rag.compliance_check import check_compliance

logger = logging.getLogger(__name__)

DRAFT_SYSTEM = (
    "You draft a suggested resolution for an engineering review comment. "
    "Use the provided similar-past-comment resolutions and standards context "
    "if relevant. If neither source is relevant, draft a reasonable generic "
    "resolution and say so explicitly. Keep it concise (2-4 sentences) and "
    "actionable. Never state something as fact unless it is supported by the "
    "provided context. "
    'Return JSON: {"draft_resolution": "...", "basis": "similar_comments" | '
    '"standards" | "both" | "generic"}'
)


def recommend_resolution(comment_text: str, llm_client, project_id: Optional[str] = None,
                          comment_id: Optional[str] = None, top_k_similar: int = 3) -> Dict:
    """
    Returns:
        {
            "draft_resolution": str,
            "basis": str,
            "similar_comments": [{"comment_id", "text", "resolution_text", "score"}, ...],
            "standards_grounding": {... same shape as check_compliance() ...} or None,
            "confidence_percent": int,   # heuristic, see below
        }
    """
    # --- Source 1: similar past comments + their resolutions ---
    similar_with_resolutions = []
    try:
        query_vector = embedder.embed_text(comment_text)
        similar = vdb.search_similar_comments(query_vector, top_k=top_k_similar, project_id=project_id)
        if similar:
            resolutions = db.get_resolution_history_for([s["comment_id"] for s in similar])
            res_by_id = {r["comment_id"]: r for r in resolutions}
            for s in similar:
                res = res_by_id.get(s["comment_id"])
                if res:
                    similar_with_resolutions.append({
                        "comment_id": s["comment_id"], "text": s["text"],
                        "resolution_text": res["resolution_text"], "score": s["score"],
                    })
    except Exception as e:
        logger.warning(f"Similarity search failed: {e}")

    # --- Source 2: standards grounding (reuses the agentic RAG module) ---
    standards_result = None
    try:
        standards_result = check_compliance(comment_text, llm_client, comment_id=comment_id)
        if standards_result["faithfulness_passed"] is not True:
            # Don't feed an unverified or not-applicable grounding into the draft
            standards_result_for_prompt = None
        else:
            standards_result_for_prompt = standards_result
    except Exception as e:
        logger.warning(f"Standards compliance check failed: {e}")
        standards_result_for_prompt = None

    # --- Build the draft prompt from whichever sources are actually usable ---
    context_parts = []
    if similar_with_resolutions:
        context_parts.append("Similar past comments and their resolutions:\n" + "\n".join(
            f"- \"{s['text']}\" -> resolved as: \"{s['resolution_text']}\""
            for s in similar_with_resolutions
        ))
    if standards_result_for_prompt:
        context_parts.append(
            f"Standards grounding (faithfulness-verified): {standards_result_for_prompt['answer']}"
        )

    user_prompt = f'Comment: "{comment_text}"\n\n' + (
        "\n\n".join(context_parts) if context_parts else "No similar past comments or standards context found."
    )

    try:
        draft = llm_client.chat_json(DRAFT_SYSTEM, user_prompt)
    except Exception as e:
        logger.warning(f"Draft generation failed: {e}")
        draft = {"draft_resolution": "Could not generate a draft — see logs.", "basis": "generic"}

    # Heuristic confidence: higher when grounded in verified sources, not a
    # model-reported probability — stated as such, not dressed up as precise.
    confidence = 40
    if similar_with_resolutions:
        confidence += 25
    if standards_result_for_prompt:
        confidence += 25
    confidence = min(confidence, 90)  # never claim near-certainty for a draft

    return {
        "draft_resolution": draft.get("draft_resolution", ""),
        "basis": draft.get("basis", "generic"),
        "similar_comments": similar_with_resolutions,
        "standards_grounding": standards_result,
        "confidence_percent": confidence,
    }

"""
recommender/resolution_recommender.py

Given a review comment, drafts a suggested resolution for a HUMAN reviewer from two kinds of
input, which are kept separate in the output because they are not equally strong:

  1. historical examples  -- semantically similar past comments and how a person resolved them
                             (precedent, NOT verified engineering evidence)
  2. standards evidence   -- excerpts from the standards corpus, used only when the agentic RAG
                             check is fully verified (citations validated in code + faithfulness)

The result is always a DRAFT: status "draft_requires_human_review", requires_human_approval
True, auto_applied False. This module never writes a resolution, never changes a comment's
status and never touches a drawing; approving/editing/rejecting happens elsewhere, by a person.

Retrieval scoping (to avoid self-matches and cross-client leakage):
  * the comment itself is excluded by id (Qdrant point id == Postgres comments.id);
  * its own revision (= its source file, after Chunk A) is excluded by default, so "history"
    really comes from other reviews;
  * results are restricted to the comment's project unless cross_project=True.

`basis` is computed from the evidence actually used; the model's own claim is reported
separately as `model_claimed_basis` and never trusted. `confidence_percent` is a capped
heuristic of evidence availability, NOT a probability of correctness.

Usage:
    from recommender.resolution_recommender import recommend_resolution
    result = recommend_resolution(comment_text, llm_client, comment_id=...)
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
    "You draft a suggested resolution for an engineering review comment, for a human reviewer "
    "to approve, edit or reject. You may be given (a) HISTORICAL EXAMPLES: how similar past "
    "comments were resolved -- precedent only, not proof -- and (b) VERIFIED STANDARD EXCERPTS. "
    "Use them only where relevant. Never state an engineering requirement as fact unless it "
    "appears in the verified excerpts; never invent clause numbers. If neither source is "
    "relevant, write a cautious generic draft and say that no supporting evidence was found. "
    "Keep it concise (2-4 sentences) and actionable. "
    'Return JSON: {"draft_resolution": "...", "basis": "similar_comments" | "standards" | "both" | "generic"}'
)

DRAFT_STATUS = "draft_requires_human_review"


def _computed_basis(has_history: bool, has_standards: bool) -> str:
    return {(True, True): "both", (True, False): "similar_comments",
            (False, True): "standards", (False, False): "generic"}[(has_history, has_standards)]


def recommend_resolution(comment_text: str, llm_client, project_id: Optional[str] = None,
                         comment_id: Optional[str] = None, top_k_similar: int = 3,
                         exclude_same_revision: bool = True, cross_project: bool = False,
                         min_similarity: float = 0.55) -> Dict:
    """
    Returns:
        {
            "status": "draft_requires_human_review" | "draft_unavailable",
            "requires_human_approval": True, "auto_applied": False,
            "draft_resolution": str,
            "basis": "both" | "similar_comments" | "standards" | "generic",   # computed
            "model_claimed_basis": str | None, "basis_mismatch": bool,
            "similar_comments": [{"comment_id", "comment_uid", "text", "resolution_text",
                                  "resolved_by", "resolution_source", "score", "revision_id",
                                  "evidence_type": "historical_example"}, ...],
            "standards_evidence": [{chunk_id, code_reference, section_reference, ...}] (verified only),
            "standards_grounding": {... check_compliance() result ...} or None,
            "corpus_status": str,
            "confidence_percent": int | None, "confidence_rationale": str,
            "uncertainty": [str, ...],
            "retrieval_scope": {...},
        }
    """
    uncertainty: List[str] = []
    scope = {"project_id": project_id, "excluded_comment_id": comment_id, "min_similarity": min_similarity,
             "excluded_revision_id": None, "cross_project": cross_project}

    # --- where does the comment live? (scopes retrieval, excludes its own revision) ---
    context = None
    if comment_id:
        try:
            context = db.get_comment_context(comment_id)
        except Exception as e:
            logger.warning(f"Comment context lookup failed: {e}")
            uncertainty.append("comment context unavailable (database error): only the comment "
                               "itself is excluded from history, not its revision")
    if context:
        if project_id is None and not cross_project:
            project_id = context.get("project_id")
            scope["project_id"] = project_id
        if exclude_same_revision:
            scope["excluded_revision_id"] = context.get("revision_id")
    if project_id is None and not cross_project:
        uncertainty.append("historical search is not scoped to a project (no project known)")

    # --- Source 1: historical examples (similar past comments + human resolutions) ---
    similar_with_resolutions: List[Dict] = []
    try:
        query_vector = embedder.embed_text(comment_text)
        similar = vdb.search_similar_comments(
            query_vector, top_k=top_k_similar, project_id=None if cross_project else project_id,
            score_threshold=min_similarity,
            exclude_ids=[comment_id] if comment_id else None,
            exclude_revision_id=scope["excluded_revision_id"])
        similar = [s for s in similar if not comment_id or s["comment_id"] != str(comment_id)]
        if similar:
            resolutions = db.get_resolution_history_for([s["comment_id"] for s in similar])
            latest: Dict[str, Dict] = {}
            for r in resolutions:                     # newest first: keep the FIRST per comment
                latest.setdefault(str(r["comment_id"]), r)
            for s in similar:
                res = latest.get(s["comment_id"])
                if res:
                    similar_with_resolutions.append({
                        "comment_id": s["comment_id"], "comment_uid": s.get("comment_uid"),
                        "text": s["text"], "resolution_text": res["resolution_text"],
                        "resolved_by": res.get("resolved_by"), "resolution_source": res.get("source"),
                        "score": s["score"], "revision_id": s.get("revision_id"),
                        "evidence_type": "historical_example",
                    })
        if not similar:
            uncertainty.append("no sufficiently similar past comment found")
        elif not similar_with_resolutions:
            uncertainty.append("similar past comments exist but none has a human-approved resolution")
    except Exception as e:
        logger.warning(f"Similarity search failed: {e}")
        uncertainty.append(f"historical search unavailable ({type(e).__name__})")

    # --- Source 2: standards grounding (reuses the agentic RAG module) ---
    standards_result, standards_evidence = None, []
    try:
        standards_result = check_compliance(comment_text, llm_client, comment_id=comment_id)
        if standards_result.get("verified") is True:
            standards_evidence = [e for e in standards_result["evidence"] if e["cited"]]
        else:
            uncertainty.append(f"standards evidence not used: {standards_result.get('evidence_status')}")
    except Exception as e:
        logger.warning(f"Standards compliance check failed: {e}")
        uncertainty.append(f"standards check unavailable ({type(e).__name__})")
    corpus_status = standards_result.get("corpus_status", "none_retrieved") if standards_result else "none_retrieved"
    if standards_evidence and corpus_status != "approved":
        uncertainty.append(f"standards corpus is {corpus_status}: excerpts are not authoritative")

    # --- Build the draft prompt from whichever sources are actually usable ---
    context_parts = []
    if similar_with_resolutions:
        context_parts.append("HISTORICAL EXAMPLES (precedent, not verified evidence):\n" + "\n".join(
            f"- \"{s['text']}\" -> resolved as: \"{s['resolution_text']}\"" for s in similar_with_resolutions))
    if standards_evidence:
        context_parts.append(
            f"VERIFIED STANDARD EXCERPTS (corpus status: {corpus_status}): {standards_result['answer']} "
            f"[sources: {', '.join(standards_result['cited_sections'])}]")
    user_prompt = f'Comment: "{comment_text}"\n\n' + (
        "\n\n".join(context_parts) if context_parts else "No similar past comments or standards context found.")

    draft_text, model_basis, status = "", None, DRAFT_STATUS
    try:
        draft = llm_client.chat_json(DRAFT_SYSTEM, user_prompt)
        if not isinstance(draft, dict) or not str(draft.get("draft_resolution") or "").strip():
            raise ValueError("model returned no draft_resolution")
        draft_text = str(draft["draft_resolution"]).strip()
        model_basis = draft.get("basis")
    except Exception as e:
        logger.warning(f"Draft generation failed: {e}")
        status = "draft_unavailable"
        draft_text = "No draft could be generated; resolve this comment manually."
        uncertainty.append(f"draft generation failed ({type(e).__name__})")

    basis = _computed_basis(bool(similar_with_resolutions), bool(standards_evidence))
    basis_mismatch = model_basis is not None and model_basis != basis
    if basis_mismatch:
        uncertainty.append(f"model claimed basis '{model_basis}' but the evidence actually used is '{basis}'")

    # Heuristic of evidence AVAILABILITY, not a probability of being right.
    if status == "draft_unavailable":
        confidence, rationale = None, "no draft was generated"
    else:
        confidence, parts = 40, ["40 base"]
        if similar_with_resolutions:
            confidence += 25
            parts.append("+25 human-resolved similar comment(s)")
        if standards_evidence:
            bonus = 25 if corpus_status == "approved" else 10
            confidence += bonus
            parts.append(f"+{bonus} verified standards excerpt(s) ({corpus_status} corpus)")
        confidence = min(confidence, 90)          # never claim near-certainty for a draft
        rationale = ", ".join(parts) + "; capped at 90; heuristic, not a probability"

    return {
        "status": status, "requires_human_approval": True, "auto_applied": False,
        "draft_resolution": draft_text,
        "basis": basis, "model_claimed_basis": model_basis, "basis_mismatch": basis_mismatch,
        "similar_comments": similar_with_resolutions,
        "standards_evidence": standards_evidence,
        "standards_grounding": standards_result,
        "corpus_status": corpus_status,
        "confidence_percent": confidence, "confidence_rationale": rationale,
        "uncertainty": uncertainty,
        "retrieval_scope": scope,
    }

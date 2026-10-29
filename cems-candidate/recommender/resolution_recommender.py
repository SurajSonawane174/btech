"""
recommender/resolution_recommender.py

Drafts a suggested resolution for a HUMAN reviewer from two kinds of input, kept separate in the
output because they are not equally strong:

  1. historical examples  -- similar past comments that a person already CLOSED with an approved
                             resolution (Qdrant payload status 'closed' + resolution_text);
                             precedent, NOT verified engineering evidence
  2. standards evidence   -- excerpts from the standards collection, used only when the agentic RAG
                             check is fully verified (citations validated in code + faithfulness)

The result is always a DRAFT: status "draft_requires_human_review", requires_human_approval True,
auto_applied False. suggest_resolution() stores ONLY comments.ai_suggested_resolution and
comments.ai_confidence_percent; resolution_text / resolved_at / status are written by a human
approval (vectordb.comment_sync.resolve_comment), never here.

There is no column for cited standards, so the stored draft ends with one line
"Referenced standards: AWS D1.1 Clause 2.4, ..."; the structured citations and the full RAG trace
are returned in the result (not stored).

Retrieval scoping:
  * the comment itself is excluded by id (Qdrant point id == comments.id);
  * its own document row (= its revision) is excluded by default;
  * results are restricted to the comment's praj_project_number unless cross_project=True.

`basis` is computed from the evidence actually used; the model's own claim is reported separately.
`confidence_percent` is a capped heuristic of evidence availability, NOT a probability; it is None
when the faithfulness check failed or no draft could be generated.
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


def referenced_standards_line(citations: List[Dict]) -> str:
    refs = []
    for c in citations:
        ref = f"{c.get('code_reference')} {c.get('section_reference')}".strip()
        if ref and ref not in refs:
            refs.append(ref)
    return f"Referenced standards: {', '.join(refs)}" if refs else ""


def recommend_resolution(comment_text: str, llm_client, praj_project_number: Optional[str] = None,
                         comment_id: Optional[int] = None, top_k_similar: int = 3,
                         exclude_same_document: bool = True, cross_project: bool = False,
                         min_similarity: float = 0.55) -> Dict:
    """
    comment_id is comments.id (bigint). Pure: reads Postgres/Qdrant, writes nothing.
    Returns:
        {
            "status": "draft_requires_human_review" | "draft_unavailable",
            "requires_human_approval": True, "auto_applied": False,
            "draft_resolution": str,               # model draft
            "stored_text": str,                    # draft + "Referenced standards: ..." line
            "basis": "both" | "similar_comments" | "standards" | "generic",   # computed
            "model_claimed_basis": str | None, "basis_mismatch": bool,
            "similar_comments": [{id, comment_id, text, resolution_text, score, document_id,
                                  praj_document_number, praj_revision_number, evidence_type}],
            "standards_evidence": [...verified evidence only...],
            "citations": [{chunk_id, code_reference, section_reference, page_number}],
            "standards_grounding": {... check_compliance() result ...} or None,
            "faithfulness_failed": bool,
            "corpus_status": str,
            "confidence_percent": int | None, "confidence_rationale": str,
            "uncertainty": [str, ...],
            "retrieval_scope": {...},
            "trace": {... RAG trace ...} or None,
        }
    """
    uncertainty: List[str] = []
    scope = {"praj_project_number": praj_project_number, "excluded_comment_id": comment_id,
             "excluded_document_id": None, "min_similarity": min_similarity, "cross_project": cross_project}

    context = None
    if comment_id is not None:
        try:
            context = db.get_comment_context(comment_id)
        except Exception as e:
            logger.warning(f"Comment context lookup failed: {e}")
            uncertainty.append("comment context unavailable (database error): only the comment "
                               "itself is excluded from history, not its revision")
    if context:
        if praj_project_number is None and not cross_project:
            praj_project_number = context.get("praj_project_number")
            scope["praj_project_number"] = praj_project_number
        if exclude_same_document:
            scope["excluded_document_id"] = context.get("document_id")
    if praj_project_number is None and not cross_project:
        uncertainty.append("historical search is not scoped to a project (no project known)")

    # --- Source 1: similar comments that a person already closed with a resolution ---
    similar: List[Dict] = []
    try:
        hits = vdb.search_similar_comments(
            embedder.embed_text(comment_text), top_k=top_k_similar, score_threshold=min_similarity,
            praj_project_number=None if cross_project else praj_project_number, only_resolved=True,
            exclude_ids=[comment_id] if comment_id else None, exclude_document_id=scope["excluded_document_id"])
        similar = [{"id": h["id"], "comment_id": h.get("comment_id"), "text": h.get("text"),
                    "resolution_text": h.get("resolution_text"), "score": h["score"],
                    "document_id": h.get("document_id"), "praj_document_number": h.get("praj_document_number"),
                    "praj_revision_number": h.get("praj_revision_number"), "evidence_type": "historical_example"}
                   for h in hits if h.get("resolution_text") and h["id"] != comment_id]
        if not similar:
            uncertainty.append("no sufficiently similar resolved comment found")
    except Exception as e:
        logger.warning(f"Similarity search failed: {e}")
        uncertainty.append(f"historical search unavailable ({type(e).__name__})")

    # --- Source 2: standards grounding (agentic RAG) ---
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
    faithfulness_failed = bool(standards_result) and standards_result.get("evidence_status") == "faithfulness_failed"
    if faithfulness_failed:
        uncertainty.append("faithfulness check failed: the standards answer was not supported by its excerpts")
    corpus_status = standards_result.get("corpus_status", "none_retrieved") if standards_result else "none_retrieved"
    if standards_evidence and corpus_status != "approved":
        uncertainty.append(f"standards corpus is {corpus_status}: excerpts are not authoritative")
    citations = [{"chunk_id": e["chunk_id"], "code_reference": e.get("code_reference"),
                  "section_reference": e.get("section_reference"), "page_number": e.get("page_number")}
                 for e in standards_evidence]

    context_parts = []
    if similar:
        context_parts.append("HISTORICAL EXAMPLES (precedent, not verified evidence):\n" + "\n".join(
            f"- \"{s['text']}\" -> resolved as: \"{s['resolution_text']}\"" for s in similar))
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

    basis = _computed_basis(bool(similar), bool(standards_evidence))
    basis_mismatch = model_basis is not None and model_basis != basis
    if basis_mismatch:
        uncertainty.append(f"model claimed basis '{model_basis}' but the evidence actually used is '{basis}'")

    if status == "draft_unavailable":
        confidence, rationale = None, "no draft was generated"
    elif faithfulness_failed:
        confidence, rationale = None, "faithfulness check failed; no confidence given"
    else:
        confidence, parts = 40, ["40 base"]
        if similar:
            confidence += 25
            parts.append("+25 human-resolved similar comment(s)")
        if standards_evidence:
            bonus = 25 if corpus_status == "approved" else 10
            confidence += bonus
            parts.append(f"+{bonus} verified standards excerpt(s) ({corpus_status} corpus)")
        confidence = min(confidence, 90)
        rationale = ", ".join(parts) + "; capped at 90; heuristic, not a probability"

    ref_line = referenced_standards_line(citations)
    stored_text = f"{draft_text}\n\n{ref_line}" if ref_line else draft_text

    return {
        "status": status, "requires_human_approval": True, "auto_applied": False,
        "draft_resolution": draft_text, "stored_text": stored_text,
        "basis": basis, "model_claimed_basis": model_basis, "basis_mismatch": basis_mismatch,
        "similar_comments": similar, "standards_evidence": standards_evidence, "citations": citations,
        "standards_grounding": standards_result, "faithfulness_failed": faithfulness_failed,
        "corpus_status": corpus_status,
        "confidence_percent": confidence, "confidence_rationale": rationale,
        "uncertainty": uncertainty, "retrieval_scope": scope,
        "trace": (standards_result or {}).get("trace"),
    }


def suggest_resolution(comment_pk: int, llm_client, **kwargs) -> Dict:
    """Run the recommender for one stored comment (comments.id) and save the DRAFT to
    ai_suggested_resolution / ai_confidence_percent. A failed draft is not saved (an earlier
    suggestion, if any, is kept). Never writes resolution_text, resolved_at or status."""
    context = db.get_comment_context(comment_pk)
    if context is None:
        raise LookupError(f"comment {comment_pk} not found")
    result = recommend_resolution(context["actual_extracted_comment"], llm_client, comment_id=comment_pk, **kwargs)
    saved = False
    if result["status"] == DRAFT_STATUS:
        saved = db.save_ai_suggestion(comment_pk, result["stored_text"], result["confidence_percent"])
    result["saved"] = saved
    return result

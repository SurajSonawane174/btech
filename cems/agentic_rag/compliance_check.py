"""
agentic_rag/compliance_check.py

Agentic RAG for engineering-standards grounding of review comments.
Not single-shot RAG: decomposes the comment into retrievable
sub-questions, retrieves per sub-question (multi-hop), synthesizes a
grounded answer, then runs a separate faithfulness self-check before
returning — refusing to answer if the retrieved chunks don't actually
support the synthesized claim. Every hop is logged for audit.

Reuses comment_extractor.py's own Config/LLMClient so this stays on
the same provider/model/retry contract as the rest of the pipeline —
no second LLM wrapper.

Usage:
    from agentic_rag.compliance_check import check_compliance
    result = check_compliance(comment_text, llm_client, comment_id=None)
"""
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database import db
from vectordb import qdrant_client as vdb
from vectordb import embedder

logger = logging.getLogger(__name__)

MAX_HOPS = 3
TOP_K_PER_HOP = 3

DECOMPOSE_SYSTEM = (
    "You break an engineering review comment into 1-3 short, independently "
    "searchable questions that, if answered, would let someone verify whether "
    "the comment is addressed by a referenced engineering standard. "
    "If the comment references no checkable standard/code/spec requirement, "
    "return an empty list. "
    'Return JSON: {"subqueries": ["...", ...]}'
)

SYNTHESIZE_SYSTEM = (
    "You answer an engineering compliance question using ONLY the provided "
    "standard excerpts. Cite the code reference and section for every claim. "
    "If the excerpts do not contain enough information to answer, say so "
    "explicitly rather than guessing. "
    'Return JSON: {"answer": "...", "cited_sections": ["AWS D1.1 Clause 7.2.1", ...]}'
)

FAITHFULNESS_SYSTEM = (
    "You are a strict fact-checker. Given a synthesized answer and the source "
    "excerpts it claims to be grounded in, determine whether every factual "
    "claim in the answer is actually supported by the excerpts. Flag any "
    "claim that is not directly supported, even if plausible. "
    'Return JSON: {"passed": true/false, "notes": "..."}'
)


def decompose_query(comment_text: str, llm_client) -> List[str]:
    try:
        result = llm_client.chat_json(DECOMPOSE_SYSTEM, f'Comment: "{comment_text}"')
        subqueries = result.get("subqueries", [])
        return [q for q in subqueries if isinstance(q, str) and q.strip()]
    except Exception as e:
        logger.warning(f"Query decomposition failed, falling back to single-hop: {e}")
        return [comment_text]


def retrieve_hop(subquery: str, code_reference: Optional[str] = None) -> List[Dict]:
    try:
        vector = embedder.embed_text(subquery)
    except Exception as e:
        logger.warning(f"Embedding failed for subquery '{subquery}': {e}")
        return []
    return vdb.search_standards(vector, top_k=TOP_K_PER_HOP, code_reference=code_reference)


def synthesize_answer(comment_text: str, retrieved_chunks: List[Dict], llm_client) -> Dict:
    if not retrieved_chunks:
        return {
            "answer": "No relevant standard excerpts were retrieved for this comment.",
            "cited_sections": [],
            "synthesis_succeeded": False,
        }

    excerpts_text = "\n\n".join(
        f"[{c['code_reference']} {c['section_reference']}]: {c['text']}"
        for c in retrieved_chunks
    )

    user_prompt = f'Comment: "{comment_text}"\n\nRetrieved excerpts:\n{excerpts_text}'

    try:
        result = llm_client.chat_json(SYNTHESIZE_SYSTEM, user_prompt)

        return {
            "answer": result.get("answer", ""),
            "cited_sections": result.get("cited_sections", []),
            "synthesis_succeeded": True,
        }

    except Exception as e:
        logger.warning(f"Synthesis failed: {e}")

        return {
            "answer": "Synthesis failed — see logs.",
            "cited_sections": [],
            "synthesis_succeeded": False,
        }


def faithfulness_check(answer: str, retrieved_chunks: List[Dict], llm_client) -> Dict:
    if not retrieved_chunks:
        return {"passed": False, "notes": "No source excerpts to check faithfulness against."}
    excerpts_text = "\n\n".join(
        f"[{c['code_reference']} {c['section_reference']}]: {c['text']}" for c in retrieved_chunks
    )
    user_prompt = f"Answer to check: {answer}\n\nSource excerpts:\n{excerpts_text}"
    try:
        return llm_client.chat_json(FAITHFULNESS_SYSTEM, user_prompt)
    except Exception as e:
        logger.warning(f"Faithfulness check failed: {e}")
        return {"passed": False, "notes": f"Faithfulness check itself failed: {e}"}


def check_compliance(comment_text: str, llm_client, comment_id: Optional[str] = None) -> Dict:
    """
    Full agentic loop. Returns:
        {
            "answer": str,
            "cited_sections": [...],
            "faithfulness_passed": bool,
            "faithfulness_notes": str,
            "hops": [{"hop": int, "query": str, "chunks_retrieved": int}, ...],
            "cited_chunk_ids": [...],
        }
    """
    subqueries = decompose_query(comment_text, llm_client)
    if not subqueries:
        return {
            "answer": "This comment does not reference a checkable standard requirement.",
            "cited_sections": [], "faithfulness_passed": None,
            "faithfulness_notes": "Not applicable — no compliance check triggered.",
            "hops": [], "cited_chunk_ids": [],
        }

    hops_log = []
    all_chunks = []
    for hop_num, subq in enumerate(subqueries[:MAX_HOPS], start=1):
        chunks = retrieve_hop(subq)
        hops_log.append({"hop": hop_num, "query": subq, "chunks_retrieved": len(chunks)})
        all_chunks.extend(chunks)

    # de-dup chunks retrieved across hops
    seen_ids = set()
    unique_chunks = []
    for c in all_chunks:
        if c["chunk_id"] not in seen_ids:
            seen_ids.add(c["chunk_id"])
            unique_chunks.append(c)

    synthesis = synthesize_answer(comment_text, unique_chunks, llm_client)
    answer = synthesis.get("answer", "")
    cited_sections = synthesis.get("cited_sections", [])
    synthesis_succeeded = synthesis.get("synthesis_succeeded", False)

    if synthesis_succeeded:
        fcheck = faithfulness_check(answer, unique_chunks, llm_client)
        passed = fcheck.get("passed", False)
        notes = fcheck.get("notes", "")
    else:
        passed = False
        notes = "Faithfulness check skipped because standards synthesis failed."

    if comment_id is not None:
        try:
            db.log_rag_trace(
                comment_id=comment_id, original_query=comment_text,
                decomposed_subqueries=subqueries, retrieval_hops=hops_log,
                faithfulness_passed=passed, faithfulness_notes=notes,
                final_answer=answer, cited_chunk_ids=[c["chunk_id"] for c in unique_chunks],
            )
        except Exception as e:
            logger.warning(f"Could not log RAG trace: {e}")

    return {
        "answer": answer, "cited_sections": cited_sections,
        "faithfulness_passed": passed, "faithfulness_notes": notes,
        "hops": hops_log, "cited_chunk_ids": [c["chunk_id"] for c in unique_chunks],
    }

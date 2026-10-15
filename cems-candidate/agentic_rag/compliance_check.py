"""
agentic_rag/compliance_check.py

Agentic RAG for engineering-standards grounding of review comments.
Not single-shot RAG: decomposes the comment into retrievable
sub-questions, retrieves per sub-question (multi-hop), synthesizes a
grounded answer, then runs a separate faithfulness self-check before
returning — refusing to answer if the retrieved chunks don't actually
support the synthesized claim. Every hop is logged for audit.

Evidence is checked IN CODE, not taken from the model's word:
  * every excerpt shown to the model gets a tag [S1], [S2] ...; the model must cite tags;
    cited_sections and cited_chunk_ids are DERIVED from valid tags, never copied from the reply;
  * a tag that was never shown, or a clause/section/table number mentioned in the answer that
    is not in any retrieved excerpt, fails citation validation;
  * the faithfulness verdict is parsed strictly (the string "false" is not a pass);
  * `verified` is True only when retrieval, synthesis, citation validation AND the faithfulness
    check all succeed; otherwise `evidence_status` says why.
Duplicate chunks (same code, section and text, e.g. a seed that was run twice) are merged with
their ids kept in `duplicate_chunk_ids`; different clauses are never merged.

The standards corpus shipped with this repo is ILLUSTRATIVE (paraphrased placeholders): every
result carries `corpus_status`, and nothing here establishes real compliance.

Reuses comment_extractor.py's own Config/LLMClient so this stays on
the same provider/model/retry contract as the rest of the pipeline —
no second LLM wrapper.

Usage:
    from agentic_rag.compliance_check import check_compliance
    result = check_compliance(comment_text, llm_client, comment_id=None)
"""
import hashlib
import re
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config_utils import strict_true
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
    "standard excerpts. Each excerpt starts with a tag such as [S1]. Support every claim "
    "with the tag(s) of the excerpt(s) it comes from, and do not mention any clause, "
    "section or table number that does not appear in the excerpts. "
    "If the excerpts do not contain enough information to answer, say so "
    "explicitly and set sufficient to false rather than guessing. "
    'Return JSON: {"answer": "...", "citations": ["S1", ...], "sufficient": true/false}'
)

FAITHFULNESS_SYSTEM = (
    "You are a strict fact-checker. Given a synthesized answer and the source "
    "excerpts it claims to be grounded in, determine whether every factual "
    "claim in the answer is actually supported by the excerpts. Flag any "
    "claim that is not directly supported, even if plausible. "
    'Return JSON: {"passed": true/false, "notes": "..."}'
)

_REF_RE = re.compile(r"\b(?:clause|section|sec\.|table|para(?:graph)?|cl\.)\s*([0-9]+(?:\.[0-9]+)*[a-z]?)", re.I)
_TAG_RE = re.compile(r"^\s*\[?\s*S\s*(\d+)\s*\]?\s*$", re.I)


# ---------------------------------------------------------------- retrieval

def decompose_query(comment_text: str, llm_client) -> List[str]:
    try:
        result = llm_client.chat_json(DECOMPOSE_SYSTEM, f'Comment: "{comment_text}"')
        subqueries = result.get("subqueries", []) if isinstance(result, dict) else []
        if not isinstance(subqueries, list):        # a bare string would be iterated per character
            raise ValueError(f"subqueries is {type(subqueries).__name__}, not a list")
        return [q.strip() for q in subqueries if isinstance(q, str) and q.strip()]
    except Exception as e:
        logger.warning(f"Query decomposition failed, falling back to single-hop: {e}")
        return [comment_text]


def retrieve_hop(subquery: str, code_reference: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
    """-> (chunks, error). An unavailable embedder or vector store is reported, not raised."""
    try:
        vector = embedder.embed_text(subquery)
    except Exception as e:
        logger.warning(f"Embedding failed for subquery '{subquery}': {e}")
        return [], f"embedding unavailable: {type(e).__name__}"
    try:
        return vdb.search_standards(vector, top_k=TOP_K_PER_HOP, code_reference=code_reference), None
    except Exception as e:
        logger.warning(f"Standards search failed for subquery '{subquery}': {e}")
        return [], f"vector search unavailable: {type(e).__name__}"


def _norm(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def dedupe_chunks(chunks: List[Dict]) -> List[Dict]:
    """Merge chunks that are the same clause (same code, section and normalised text), keeping
    the best score and the other chunk ids as provenance. Distinct clauses stay separate."""
    merged: Dict[Tuple, Dict] = {}
    order: List[Tuple] = []
    for c in sorted(chunks, key=lambda c: -(c.get("score") or 0.0)):
        key = (_norm(c.get("code_reference")), _norm(c.get("section_reference")),
               hashlib.sha1(_norm(c.get("text")).encode()).hexdigest())
        if key not in merged:
            merged[key] = dict(c, duplicate_chunk_ids=[])
            order.append(key)
        elif c["chunk_id"] != merged[key]["chunk_id"] and c["chunk_id"] not in merged[key]["duplicate_chunk_ids"]:
            merged[key]["duplicate_chunk_ids"].append(c["chunk_id"])
    return [merged[k] for k in order]


def corpus_status_of(chunks: List[Dict]) -> str:
    statuses = set()
    for c in chunks:
        s = c.get("corpus_status") or "unknown"
        if s == "unknown" and "illustrative" in (c.get("title") or "").lower():
            s = "illustrative_placeholder"
        statuses.add(s)
    if not statuses:
        return "none_retrieved"
    if "illustrative_placeholder" in statuses:
        return "illustrative_placeholder"
    return "approved" if statuses == {"approved"} else "unknown"


# ---------------------------------------------------------------- synthesis + validation

def _excerpts(chunks: List[Dict]) -> str:
    return "\n\n".join(f"[S{i}] [{c['code_reference']} {c['section_reference']}]: {c['text']}"
                       for i, c in enumerate(chunks, start=1))


def synthesize_answer(comment_text: str, retrieved_chunks: List[Dict], llm_client) -> Dict:
    if not retrieved_chunks:
        return {"answer": "No relevant standard excerpts were retrieved for this comment.",
                "citations": [], "sufficient": False, "synthesis_succeeded": False}
    user_prompt = f'Comment: "{comment_text}"\n\nRetrieved excerpts:\n{_excerpts(retrieved_chunks)}'
    try:
        result = llm_client.chat_json(SYNTHESIZE_SYSTEM, user_prompt)
        if not isinstance(result, dict):
            raise ValueError("synthesis reply is not a JSON object")
        answer = result.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("synthesis reply has no answer text")
        citations = result.get("citations", [])
        return {"answer": answer.strip(),
                "citations": citations if isinstance(citations, list) else [citations],
                "sufficient": strict_true(result.get("sufficient", True)),
                "synthesis_succeeded": True}
    except Exception as e:
        logger.warning(f"Synthesis failed: {e}")
        return {"answer": "Synthesis failed — see logs.", "citations": [], "sufficient": False,
                "synthesis_succeeded": False}


def validate_citations(answer: str, citations: List, chunks: List[Dict]) -> Dict:
    """
    Code-side evidence check. Returns
      valid_tags                   tags that point at an excerpt that was actually shown
      invalid_citations            tags/strings that do not (never-retrieved or malformed)
      unsupported_section_mentions clause/section/table numbers in the answer that appear in
                                   none of the retrieved excerpts (possible fabricated clause)
    """
    valid, invalid = [], []
    for c in citations:
        m = _TAG_RE.match(str(c))
        if m and 1 <= int(m.group(1)) <= len(chunks):
            tag = f"S{int(m.group(1))}"
            if tag not in valid:
                valid.append(tag)
        else:
            invalid.append(str(c)[:60])
    known_refs = set()
    for c in chunks:
        known_refs.update(n.lower() for n in _REF_RE.findall(f"{c.get('section_reference', '')} {c.get('text', '')}"))
        sec = _norm(c.get("section_reference"))
        if sec:
            known_refs.add(sec.split()[-1])
    mentioned = [n.lower() for n in _REF_RE.findall(answer or "")]
    unsupported = sorted({n for n in mentioned if n not in known_refs})
    return {"valid_tags": valid, "invalid_citations": invalid, "unsupported_section_mentions": unsupported}


def faithfulness_check(answer: str, retrieved_chunks: List[Dict], llm_client) -> Dict:
    if not retrieved_chunks:
        return {"passed": False, "notes": "No source excerpts to check faithfulness against."}
    user_prompt = f"Answer to check: {answer}\n\nSource excerpts:\n{_excerpts(retrieved_chunks)}"
    try:
        result = llm_client.chat_json(FAITHFULNESS_SYSTEM, user_prompt)
        if not isinstance(result, dict):
            raise ValueError("faithfulness reply is not a JSON object")
        raw = result.get("passed", False)
        passed = strict_true(raw)
        notes = str(result.get("notes", ""))
        if not isinstance(raw, bool) and passed is False and str(raw).strip().lower() not in ("false", "no", "0", "n", "off"):
            notes = f"unparseable verdict {raw!r} treated as not passed. {notes}"
        return {"passed": passed, "notes": notes}
    except Exception as e:
        logger.warning(f"Faithfulness check failed: {e}")
        return {"passed": False, "notes": f"Faithfulness check itself failed: {e}"}


# ---------------------------------------------------------------- main loop

def check_compliance(comment_text: str, llm_client, comment_id: Optional[str] = None) -> Dict:
    """
    Full agentic loop. Returns:
        {
            "answer": str,
            "verified": bool,                 # True only if every gate below passed
            "evidence_status": str,           # verified | not_applicable | retrieval_failed |
                                              # no_evidence | synthesis_failed |
                                              # insufficient_evidence | citation_invalid |
                                              # faithfulness_failed
            "cited_sections": [...],          # derived from valid citation tags
            "cited_chunk_ids": [...],         # chunks actually cited (validated)
            "retrieved_chunk_ids": [...],     # everything retrieved (after de-duplication)
            "evidence": [{tag, chunk_id, code_reference, section_reference, title, score,
                          corpus_status, duplicate_chunk_ids}, ...],
            "citation_check": {...},          # see validate_citations
            "faithfulness_passed": bool | None,
            "faithfulness_notes": str,
            "hops": [{"hop", "query", "chunks_retrieved", "error"}, ...],
            "corpus_status": str,             # illustrative_placeholder | approved | unknown | none_retrieved
        }
    """
    def result(answer, status, *, cited_tags=(), chunks=(), check=None, fpassed=None, fnotes="", hops=()):
        tag_map = {f"S{i}": c for i, c in enumerate(chunks, start=1)}
        cited = [tag_map[t] for t in cited_tags if t in tag_map]
        return {
            "answer": answer, "verified": status == "verified", "evidence_status": status,
            "cited_sections": [f"{c['code_reference']} {c['section_reference']}" for c in cited],
            "cited_chunk_ids": [c["chunk_id"] for c in cited],
            "retrieved_chunk_ids": [c["chunk_id"] for c in chunks],
            "evidence": [{"tag": t, "chunk_id": c["chunk_id"], "code_reference": c.get("code_reference"),
                          "section_reference": c.get("section_reference"), "title": c.get("title"),
                          "score": c.get("score"), "corpus_status": c.get("corpus_status", "unknown"),
                          "duplicate_chunk_ids": c.get("duplicate_chunk_ids", []),
                          "cited": t in cited_tags} for t, c in tag_map.items()],
            "citation_check": check or {"valid_tags": [], "invalid_citations": [],
                                        "unsupported_section_mentions": []},
            "faithfulness_passed": fpassed, "faithfulness_notes": fnotes,
            "hops": list(hops), "corpus_status": corpus_status_of(list(chunks)),
        }

    subqueries = decompose_query(comment_text, llm_client)
    if not subqueries:
        return result("This comment does not reference a checkable standard requirement.", "not_applicable",
                      fnotes="Not applicable — no compliance check triggered.")

    hops_log, all_chunks, errors = [], [], []
    for hop_num, subq in enumerate(subqueries[:MAX_HOPS], start=1):
        chunks, err = retrieve_hop(subq)
        hops_log.append({"hop": hop_num, "query": subq, "chunks_retrieved": len(chunks), "error": err})
        all_chunks.extend(chunks)
        if err:
            errors.append(err)
    unique_chunks = dedupe_chunks(all_chunks)

    if not unique_chunks:
        status = "retrieval_failed" if errors else "no_evidence"
        msg = ("Standards retrieval failed: " + "; ".join(sorted(set(errors)))) if errors \
            else "No relevant standard excerpts were retrieved for this comment."
        out = result(msg, status, hops=hops_log, fpassed=False, fnotes="Faithfulness check skipped: no evidence.")
    else:
        synthesis = synthesize_answer(comment_text, unique_chunks, llm_client)
        answer = synthesis["answer"]
        if not synthesis["synthesis_succeeded"]:
            out = result(answer, "synthesis_failed", chunks=unique_chunks, hops=hops_log, fpassed=False,
                         fnotes="Faithfulness check skipped because standards synthesis failed.")
        else:
            check = validate_citations(answer, synthesis["citations"], unique_chunks)
            common = dict(cited_tags=check["valid_tags"], chunks=unique_chunks, check=check, hops=hops_log)
            if check["invalid_citations"] or check["unsupported_section_mentions"]:
                out = result(answer, "citation_invalid", fpassed=False,
                             fnotes="Faithfulness check skipped: citations failed code-side validation.", **common)
            elif not synthesis["sufficient"] or not check["valid_tags"]:
                why = "model reported insufficient evidence" if not synthesis["sufficient"] \
                    else "answer cites no retrieved excerpt"
                out = result(answer, "insufficient_evidence", fpassed=False,
                             fnotes=f"Faithfulness check skipped: {why}.", **common)
            else:
                cited_chunks = [unique_chunks[int(t[1:]) - 1] for t in check["valid_tags"]]
                fcheck = faithfulness_check(answer, cited_chunks, llm_client)
                status = "verified" if fcheck["passed"] else "faithfulness_failed"
                out = result(answer, status, fpassed=fcheck["passed"], fnotes=fcheck["notes"], **common)

    if comment_id is not None:
        try:
            db.log_rag_trace(
                comment_id=comment_id, original_query=comment_text,
                decomposed_subqueries=subqueries, retrieval_hops=hops_log,
                faithfulness_passed=out["faithfulness_passed"],
                faithfulness_notes=f"[{out['evidence_status']}] {out['faithfulness_notes']}",
                final_answer=out["answer"], cited_chunk_ids=out["cited_chunk_ids"],
            )
        except Exception as e:
            logger.warning(f"Could not log RAG trace: {e}")
    return out

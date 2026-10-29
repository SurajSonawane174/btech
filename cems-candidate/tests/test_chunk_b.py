"""
Chunk B regression tests: boolean parsing, classification robustness, code-side citation
validation, chunk de-duplication, self-match exclusion, retrieval scoping, recommendation
safety and graceful degradation.

Deterministic: fake LLM and fake embeddings. The retrieval-filter tests use a REAL Qdrant
running in-memory (qdrant-client local mode, no server) and are skipped if qdrant-client is
not installed. Nothing here proves model quality; it proves the control flow and the gates.
"""
import dataclasses
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config_utils import parse_bool, strict_true  # noqa: E402


# ================================================================ booleans

@pytest.mark.parametrize("v,expected", [
    (True, True), (False, False), (1, True), (0, False), ("true", True), ("True", True), ("yes", True),
    ("on", True), ("1", True), ("false", False), ("FALSE", False), ("0", False), ("no", False),
    ("off", False), (" n ", False), (None, "default"), ("", "default")])
def test_parse_bool_accepts_the_usual_spellings(v, expected):
    want = True if expected == "default" else expected
    assert parse_bool(v, True, "x") is want


@pytest.mark.parametrize("bad", ["maybe", "ture", "2", 2, -1, 0.5, [], {}])
def test_parse_bool_rejects_garbage_with_the_setting_name(bad):
    with pytest.raises(ValueError, match="vision.enabled"):
        parse_bool(bad, False, "vision.enabled")


@pytest.mark.parametrize("v", ["false", "False", "0", "no", "off", "", None, "maybe", "passed?", [], 0])
def test_strict_true_fails_closed(v):
    assert strict_true(v) is False


def test_quoted_false_in_config_is_false_and_garbage_stops_the_run(tmp_path):
    import comment_extractor as ce
    y = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    y["vision"]["enabled"] = "false"                       # quoted string, as an editor might write it
    y["llm"]["metadata_enabled"] = "off"
    y.setdefault("ocr", {})["full_page"] = "0"
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(y), encoding="utf-8")
    cfg = ce.Config.from_yaml(p)
    assert (cfg.vision_enabled, cfg.metadata_llm_enabled, cfg.ocr_full_page) == (False, False, False)
    assert not cfg.llm_needed()
    y["vision"]["enabled"] = "flase"
    p.write_text(yaml.safe_dump(y), encoding="utf-8")
    with pytest.raises(ValueError, match="vision.enabled"):
        ce.Config.from_yaml(p)


# ================================================================ classification

class _ClassifierLLM:
    def __init__(self, reply):
        self.reply = reply

    def chat_json(self, system, user):
        return self.reply


def test_classifier_ignores_ids_outside_its_batch_and_survives_bad_rows():
    import comment_extractor as ce
    batch = [(10, "Font too small"), (11, "Verify weld size")]
    reply = {"results": [{"id": 10, "category": "aesthetic"},
                         {"id": 99, "category": "aesthetic"},      # foreign id: must not leak
                         {"category": "technical"},               # malformed row
                         {"id": "x", "category": "technical"},    # malformed id
                         {"id": 11, "category": "technical"}]}
    out = ce.classify_batch(_ClassifierLLM(reply), batch)
    assert out == {10: ("aesthetic", "llm"), 11: ("technical", "llm")}


def test_repeated_comment_links_to_its_original(tmp_path, monkeypatch):
    import fitz
    import comment_extractor as ce
    monkeypatch.chdir(tmp_path)
    pdf = tmp_path / "PRJ_PID_DWG101_RA.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    for pos, text in [((100, 100), "Verify fillet weld size per AWS D1.1"),
                      ((300, 300), "Relocate valve V-12"),
                      ((500, 450), "Verify fillet weld size per AWS D1.1.")]:
        a = page.add_text_annot(pos, text)
        a.update()
    doc.save(pdf)
    cfg = dataclasses.replace(ce.Config.from_yaml(ROOT / "config.yaml"), vision_enabled=False,
                              metadata_llm_enabled=False, classification_llm_enabled=False)
    _, df = ce.process_pdf(pdf, cfg, None, False)
    assert list(df.comment_category) == ["technical", "technical", "repeated"]
    assert df.duplicate_of.iloc[2] == df.comment_id.iloc[0]
    assert list(df.duplicate_of.iloc[:2]) == ["", ""]


# ================================================================ RAG: fakes

def chunk(cid, code="AWS D1.1", sec="Clause 2.4", text="Fillet weld size shall be based on the thinner part.",
          score=0.9, title="AWS D1.1 (illustrative excerpt)", status=None):
    c = {"chunk_id": cid, "score": score, "text": text, "code_reference": code,
         "section_reference": sec, "title": title}
    if status:
        c["corpus_status"] = status
    return c


class RagLLM:
    """Routes on the system prompt. Each field can be a value or an Exception to raise."""

    def __init__(self, subqueries=("fillet weld size rule",), synth=None, verdict=True, draft=None):
        self.subqueries, self.verdict = subqueries, verdict
        self.synth = synth if synth is not None else {
            "answer": "Per [S1], fillet weld size follows the thinner part (AWS D1.1 Clause 2.4).",
            "citations": ["S1"], "sufficient": True}
        self.draft = draft if draft is not None else {"draft_resolution": "Resize the weld per Clause 2.4.",
                                                      "basis": "standards"}
        self.calls = []

    def chat_json(self, system, user):
        kind = ("decompose" if "searchable questions" in system else "synth" if "ONLY the provided" in system
                else "faith" if "fact-checker" in system else "draft" if "draft a suggested" in system else "?")
        self.calls.append((kind, user))
        value = {"decompose": {"subqueries": list(self.subqueries)} if not isinstance(self.subqueries, Exception)
                 else self.subqueries, "synth": self.synth,
                 "faith": {"passed": self.verdict, "notes": "checked"}, "draft": self.draft}[kind]
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def rag(monkeypatch):
    from agentic_rag import compliance_check as cc
    store = {"chunks": [chunk("c1")], "search_error": None, "embed_error": None}

    def search_standards(vector, top_k=5, code_reference=None):
        if store["search_error"]:
            raise store["search_error"]
        return [dict(c) for c in store["chunks"]]

    def embed_text(text):
        if store["embed_error"]:
            raise store["embed_error"]
        return [0.1] * 768
    monkeypatch.setattr(cc.vdb, "search_standards", search_standards, raising=False)
    monkeypatch.setattr(cc.embedder, "embed_text", embed_text, raising=False)
    return cc, store


# ================================================================ RAG: gates

def test_verified_only_when_every_gate_passes(rag):
    cc, store = rag
    r = cc.check_compliance("Weld size not per AWS D1.1", RagLLM())
    assert r["verified"] is True and r["evidence_status"] == "verified"
    assert r["cited_chunk_ids"] == ["c1"] and r["cited_sections"] == ["AWS D1.1 Clause 2.4"]
    assert r["corpus_status"] == "illustrative_placeholder"


@pytest.mark.parametrize("verdict", ["false", "False", "0", "no", "maybe", None, {}])
def test_string_false_verdict_is_never_a_pass(rag, verdict):
    cc, _ = rag
    r = cc.check_compliance("Weld size not per AWS D1.1", RagLLM(verdict=verdict))
    assert r["verified"] is False and r["faithfulness_passed"] is False
    assert r["evidence_status"] == "faithfulness_failed"


def test_citation_to_a_chunk_that_was_never_retrieved_is_rejected(rag):
    cc, _ = rag
    synth = {"answer": "Per [S7], weld size is fixed.", "citations": ["S7", "AWS D1.1 Clause 9.9"], "sufficient": True}
    llm = RagLLM(synth=synth)
    r = cc.check_compliance("Weld size not per AWS D1.1", llm)
    assert r["evidence_status"] == "citation_invalid" and r["verified"] is False
    assert set(r["citation_check"]["invalid_citations"]) == {"S7", "AWS D1.1 Clause 9.9"}
    assert r["cited_chunk_ids"] == []
    assert not any(k == "faith" for k, _ in llm.calls)            # no LLM "verification" of bad evidence


def test_fabricated_clause_number_in_answer_is_rejected(rag):
    cc, _ = rag
    synth = {"answer": "Per [S1] and Clause 5.3.2, the weld must be 8 mm.", "citations": ["S1"], "sufficient": True}
    r = cc.check_compliance("Weld size not per AWS D1.1", RagLLM(synth=synth))
    assert r["evidence_status"] == "citation_invalid"
    assert r["citation_check"]["unsupported_section_mentions"] == ["5.3.2"]


def test_answer_without_citations_or_marked_insufficient_is_not_evidence(rag):
    cc, _ = rag
    no_cite = cc.check_compliance("x", RagLLM(synth={"answer": "Probably fine.", "citations": [], "sufficient": True}))
    insufficient = cc.check_compliance("x", RagLLM(synth={"answer": "The excerpts do not say.",
                                                          "citations": ["S1"], "sufficient": "false"}))
    assert no_cite["evidence_status"] == insufficient["evidence_status"] == "insufficient_evidence"
    assert not no_cite["verified"] and not insufficient["verified"]


def test_duplicate_chunks_are_merged_distinct_clauses_kept(rag):
    cc, store = rag
    store["chunks"] = [chunk("c1", score=0.9), chunk("c1-dup", score=0.8),           # seed run twice
                       chunk("c2", sec="Clause 7.2.1", text="All welds shall be visually inspected.", score=0.7),
                       chunk("c3", sec="Clause 2.4", text="A different paragraph of the same clause.", score=0.6)]
    r = cc.check_compliance("Weld size", RagLLM())
    assert r["retrieved_chunk_ids"] == ["c1", "c2", "c3"]
    assert r["evidence"][0]["duplicate_chunk_ids"] == ["c1-dup"]


@pytest.mark.parametrize("which", ["search_error", "embed_error"])
def test_unavailable_vector_store_or_embedder_is_reported_not_raised(rag, which):
    cc, store = rag
    store[which] = ConnectionError("down")
    r = cc.check_compliance("Weld size not per AWS D1.1", RagLLM())
    assert r["evidence_status"] == "retrieval_failed" and r["verified"] is False
    assert r["hops"][0]["error"]


def test_llm_failures_never_become_verified(rag):
    cc, _ = rag
    r1 = cc.check_compliance("x", RagLLM(synth=RuntimeError("429")))
    r2 = cc.check_compliance("x", RagLLM(synth={"answer": "", "citations": ["S1"]}))
    r3 = cc.check_compliance("x", RagLLM(subqueries=RuntimeError("timeout")))     # falls back to 1 hop
    assert r1["evidence_status"] == r2["evidence_status"] == "synthesis_failed"
    assert r3["evidence_status"] == "verified" and len(r3["hops"]) == 1


def test_string_subqueries_are_not_split_into_characters(rag):
    cc, _ = rag
    llm = RagLLM()
    llm.subqueries = None
    llm.chat_json_orig = llm.chat_json
    llm.chat_json = lambda s, u: {"subqueries": "fillet weld size"} if "searchable" in s else llm.chat_json_orig(s, u)
    r = cc.check_compliance("Weld size", llm)
    assert len(r["hops"]) == 1 and r["hops"][0]["query"] == "Weld size"


def test_no_checkable_requirement_is_not_applicable(rag):
    cc, _ = rag
    r = cc.check_compliance("Font too small", RagLLM(subqueries=()))
    assert r["evidence_status"] == "not_applicable" and r["faithfulness_passed"] is None


# ================================================================ recommender

@pytest.fixture
def rec(rag, monkeypatch):
    cc, store = rag
    from recommender import resolution_recommender as rr
    state = {"hits": [], "context": None, "search_kwargs": None, "context_error": None, "saved": []}

    def search_similar_comments(vec, top_k=5, score_threshold=0.55, praj_project_number=None,
                                comment_category=None, only_resolved=False, exclude_ids=None,
                                exclude_document_id=None):
        state["search_kwargs"] = {"praj_project_number": praj_project_number, "exclude_ids": exclude_ids,
                                  "exclude_document_id": exclude_document_id, "only_resolved": only_resolved}
        return [dict(h) for h in state["hits"]]

    def get_comment_context(cid):
        if state["context_error"]:
            raise state["context_error"]
        return state["context"]

    def forbidden(*a, **k):
        raise AssertionError("the recommender must never resolve a comment")

    monkeypatch.setattr(rr.vdb, "search_similar_comments", search_similar_comments, raising=False)
    monkeypatch.setattr(rr.embedder, "embed_text", lambda t: [0.1] * 768, raising=False)
    monkeypatch.setattr(rr.db, "get_comment_context", get_comment_context, raising=False)
    monkeypatch.setattr(rr.db, "save_ai_suggestion",
                        lambda cid, text, conf: state["saved"].append((cid, text, conf)) or True, raising=False)
    monkeypatch.setattr(rr.db, "resolve_comment", forbidden, raising=False)
    monkeypatch.setattr(rr.db, "reopen_comment", forbidden, raising=False)
    return rr, state, store


def hit(pk, text="Weld size wrong", score=0.9, doc=3, resolution="Weld resized to 6 mm."):
    return {"id": pk, "score": score, "text": text, "document_id": doc, "comment_id": f"UID-{pk}",
            "status": "closed" if resolution else "open", "resolution_text": resolution}


def test_comment_never_matches_itself_and_its_document_is_excluded(rec):
    rr, state, _ = rec
    state["context"] = {"id": 10, "document_id": 5, "praj_project_number": "P1"}
    state["hits"] = [hit(10, doc=5), hit(11)]                          # store returned self anyway
    r = rr.recommend_resolution("Weld size wrong", RagLLM(), comment_id=10)
    assert [s["id"] for s in r["similar_comments"]] == [11]
    assert state["search_kwargs"] == {"praj_project_number": "P1", "exclude_ids": [10],
                                      "exclude_document_id": 5, "only_resolved": True}


def test_cross_project_is_opt_in(rec):
    rr, state, _ = rec
    state["context"] = {"id": 10, "document_id": 5, "praj_project_number": "P1"}
    rr.recommend_resolution("x", RagLLM(), comment_id=10, cross_project=True)
    assert state["search_kwargs"]["praj_project_number"] is None


def test_only_comments_with_an_approved_resolution_are_history(rec):
    rr, state, _ = rec
    state["hits"] = [hit(11, resolution=None), hit(12, resolution="Weld resized to 8 mm.")]
    r = rr.recommend_resolution("Weld size wrong", RagLLM(), praj_project_number="P1")
    assert [s["id"] for s in r["similar_comments"]] == [12]
    assert r["similar_comments"][0]["resolution_text"] == "Weld resized to 8 mm."


def test_draft_is_always_a_human_review_draft_with_separate_evidence(rec):
    rr, state, _ = rec
    state["hits"] = [hit(11, resolution="Weld resized.")]
    llm = RagLLM(draft={"draft_resolution": "Resize weld.", "basis": "generic"})
    r = rr.recommend_resolution("Weld size not per AWS D1.1", llm, praj_project_number="P1")
    assert (r["status"], r["requires_human_approval"], r["auto_applied"]) == ("draft_requires_human_review", True, False)
    assert r["basis"] == "both" and r["model_claimed_basis"] == "generic" and r["basis_mismatch"] is True
    assert r["similar_comments"][0]["evidence_type"] == "historical_example"
    assert [e["chunk_id"] for e in r["standards_evidence"]] == ["c1"]
    assert r["citations"] == [{"chunk_id": "c1", "code_reference": "AWS D1.1", "section_reference": "Clause 2.4",
                               "page_number": None}]
    assert r["stored_text"] == "Resize weld.\n\nReferenced standards: AWS D1.1 Clause 2.4"
    assert r["draft_resolution"] == "Resize weld."
    assert r["confidence_percent"] == 75                     # 40 + 25 history + 10 (illustrative corpus)
    assert any("not authoritative" in u for u in r["uncertainty"])
    assert r["trace"]["subqueries"] == ["fillet weld size rule"] and r["trace"]["cited_chunk_ids"] == ["c1"]
    draft_prompt = next(u for k, u in llm.calls if k == "draft")
    assert "HISTORICAL EXAMPLES (precedent, not verified evidence)" in draft_prompt


def test_failed_faithfulness_is_flagged_and_gets_no_confidence(rec):
    rr, state, _ = rec
    r = rr.recommend_resolution("Weld size", RagLLM(verdict="false"), praj_project_number="P1")
    assert r["standards_evidence"] == [] and r["basis"] == "generic" and r["citations"] == []
    assert r["faithfulness_failed"] is True and r["confidence_percent"] is None
    assert r["status"] == "draft_requires_human_review"           # the draft is still returned
    assert "Referenced standards" not in r["stored_text"]


def test_services_down_degrade_to_an_explicit_uncertain_draft(rec):
    rr, state, store = rec
    state["context_error"] = ConnectionError("postgres down")
    state["hits"] = [hit(11)]
    store["search_error"] = ConnectionError("qdrant down")
    rr.vdb.search_similar_comments = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("qdrant down"))
    r = rr.recommend_resolution("Weld size", RagLLM(), comment_id=10)
    assert r["status"] == "draft_requires_human_review" and r["basis"] == "generic"
    joined = " | ".join(r["uncertainty"])
    assert "context unavailable" in joined and "historical search unavailable" in joined
    assert "retrieval_failed" in joined


def test_llm_down_gives_draft_unavailable_not_a_fake_draft(rec):
    rr, _, _ = rec
    r = rr.recommend_resolution("Weld size", RagLLM(draft=RuntimeError("429"), subqueries=()), praj_project_number="p")
    assert r["status"] == "draft_unavailable" and r["confidence_percent"] is None
    assert r["requires_human_approval"] is True


def test_suggest_resolution_stores_only_the_ai_draft(rec):
    rr, state, _ = rec
    state["context"] = {"id": 10, "document_id": 5, "praj_project_number": "P1",
                        "actual_extracted_comment": "Weld size not per AWS D1.1"}
    state["hits"] = [hit(11, resolution="Weld resized.")]
    r = rr.suggest_resolution(10, RagLLM())
    assert r["saved"] is True
    assert state["saved"] == [(10, "Resize the weld per Clause 2.4.\n\nReferenced standards: AWS D1.1 Clause 2.4", 75)]


def test_suggest_resolution_does_not_overwrite_with_a_failed_draft(rec):
    rr, state, _ = rec
    state["context"] = {"id": 10, "document_id": 5, "praj_project_number": "P1", "actual_extracted_comment": "x"}
    r = rr.suggest_resolution(10, RagLLM(draft=RuntimeError("429"), subqueries=()))
    assert r["saved"] is False and state["saved"] == []
    state["context"] = None
    with pytest.raises(LookupError):
        rr.suggest_resolution(99, RagLLM())


# ================================================================ embedder

def test_embedder_imports_without_ollama_and_check_ready_reads_new_style_listing(monkeypatch):
    spec = importlib.util.spec_from_file_location("embedder_under_test", ROOT / "vectordb/embedder.py")
    emb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(emb)                               # no `import ollama` at import time

    class Model:
        def __init__(self, model):
            self.model = model

    class Listing:
        models = [Model("nomic-embed-text:latest")]

    class Client:
        def list(self):
            return Listing()

        def embeddings(self, model, prompt):
            if prompt == "boom":
                raise ConnectionError("down")
            return {"embedding": [0.0] * 768}

    monkeypatch.setattr(emb, "_client", Client())
    assert emb.check_ready() is True
    assert emb.embed_batch(["ok", "boom"])[1] is None          # no all-zero placeholder vector


# ================================================================ real in-memory Qdrant

def _real_qdrant_module():
    pytest.importorskip("qdrant_client")
    spec = importlib.util.spec_from_file_location("qdrant_under_test", ROOT / "vectordb/qdrant_client.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from qdrant_client import QdrantClient
    mod._client = QdrantClient(location=":memory:")
    mod.ensure_collections()
    return mod


def _vec(*xs):
    v = [0.0] * 768
    for i, x in enumerate(xs):
        v[i] = x
    return v


def _payload(doc, project="P1", status="open", category="technical", resolution=None, text="weld"):
    p = {"comment_id": f"UID-{doc}", "document_id": doc, "praj_project_number": project,
         "praj_document_number": "DWG1", "praj_revision_number": "RA", "comment_category": category,
         "is_client_comment": True, "status": status, "text": text}
    if resolution:
        p["resolution_text"] = resolution
    return p


def test_real_qdrant_integer_ids_filters_and_exclusions():
    vdb = _real_qdrant_module()
    vdb.upsert_comment_points([
        {"id": 1, "vector": _vec(1, 0), "payload": _payload(doc=5)},                                   # self
        {"id": 2, "vector": _vec(1, 0.05), "payload": _payload(doc=5, status="closed", resolution="r2")},  # same doc
        {"id": 3, "vector": _vec(1, 0.1), "payload": _payload(doc=7, status="closed", resolution="r3")},
        {"id": 4, "vector": _vec(1, 0.02), "payload": _payload(doc=9, project="P2", status="closed", resolution="r4")},
        {"id": 5, "vector": _vec(1, 0.03), "payload": _payload(doc=7)},                                 # not resolved
        {"id": 6, "vector": _vec(1, 0.04), "payload": _payload(doc=7, category="aesthetic", status="closed",
                                                                 resolution="r6")},
    ])
    hits = vdb.search_similar_comments(_vec(1, 0), top_k=5, score_threshold=0.0, praj_project_number="P1",
                                       only_resolved=True, exclude_ids=[1], exclude_document_id=5)
    assert [h["id"] for h in hits] == [6, 3]
    assert hits[1]["resolution_text"] == "r3" and hits[1]["document_id"] == 7 and hits[1]["comment_id"] == "UID-7"
    tech = vdb.search_similar_comments(_vec(1, 0), top_k=5, score_threshold=0.0, praj_project_number="P1",
                                       comment_category="technical", only_resolved=True, exclude_ids=[1],
                                       exclude_document_id=5)
    assert [h["id"] for h in tech] == [3]
    assert len(vdb.search_similar_comments(_vec(1, 0), top_k=10, score_threshold=0.0)) == 6   # no filter
    with pytest.raises(ValueError):
        vdb.upsert_comment_points([{"id": "not-a-number", "vector": _vec(1), "payload": {}}])
    with pytest.raises(ValueError):
        vdb.upsert_comment_points([{"id": 0, "vector": _vec(1), "payload": {}}])


def test_real_qdrant_payload_update_on_resolve_and_reopen():
    vdb = _real_qdrant_module()
    vdb.upsert_comment_points([{"id": 3, "vector": _vec(1, 0), "payload": _payload(doc=7)}])
    vdb.update_comment_payload(3, {"status": "closed", "resolution_text": "Weld resized."})
    assert [h["id"] for h in vdb.search_similar_comments(_vec(1, 0), score_threshold=0.0, only_resolved=True)] == [3]
    vdb.update_comment_payload(3, {"status": "open"}, remove_keys=["resolution_text"])
    assert vdb.search_similar_comments(_vec(1, 0), score_threshold=0.0, only_resolved=True) == []
    point = vdb.get_client().retrieve(vdb.COMMENTS_COLLECTION, ids=[3])[0]
    assert "resolution_text" not in point.payload and point.payload["status"] == "open"


def test_real_qdrant_reseeded_standards_collapse_to_one_piece_of_evidence(monkeypatch):
    vdb = _real_qdrant_module()
    from agentic_rag import compliance_check as cc
    text = "Fillet weld size shall be based on the thinner part."

    def item(pid, vec, txt, sec):
        return {"id": pid, "vector": vec, "payload": {"chunk_text": txt, "code_reference": "AWS D1.1",
                "section_reference": sec, "page_number": None, "title": "AWS D1.1 (illustrative excerpt)",
                "corpus_status": "illustrative_placeholder"}}
    vdb.upsert_standards_points([item(101, _vec(1, 0, 0), text, "Clause 2.4"),          # the same clause twice
                                 item(102, _vec(1, 0, 0.01), text, "Clause 2.4"),
                                 item(103, _vec(1, 0.2), "All welds shall be inspected.", "Clause 7.2.1")])
    monkeypatch.setattr(cc, "vdb", vdb)
    monkeypatch.setattr(cc.embedder, "embed_text", lambda t: _vec(1, 0), raising=False)
    r = cc.check_compliance("Weld size not per AWS D1.1", RagLLM(), comment_id=10)
    assert len(r["retrieved_chunk_ids"]) == 2                  # 3 points, 2 distinct clauses
    assert all(isinstance(i, int) for i in r["retrieved_chunk_ids"])
    assert len(r["evidence"][0]["duplicate_chunk_ids"]) == 1
    assert r["corpus_status"] == "illustrative_placeholder" and r["verified"] is True
    assert r["trace"]["comment_id"] == 10 and r["trace"]["hops"][0]["chunk_ids"]


# ================================================================ OCR smoke script safety

def test_ocr_smoke_test_refuses_to_download_without_confirmation(capsys):
    sys.path.insert(0, str(ROOT / "scripts"))
    import ocr_smoke_test
    assert ocr_smoke_test.main([]) == 2
    assert "Refusing to run" in capsys.readouterr().out

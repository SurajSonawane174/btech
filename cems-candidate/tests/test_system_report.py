"""
generate_system_report.py: gate logic and report honesty.

The old report printed a hard-coded "Implemented and verified tonight" list (including RBAC) no
matter what happened. These tests pin that a check which failed, errored, was not configured or
found no data can never produce a passing verdict, and that the PDF states the computed verdict.
"""
import os
import sys
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_system_report as rep  # noqa: E402  (import must not run any check)

DSN = os.getenv("CEMS_TEST_DATABASE_URL")


def ok(data):
    return {"ran": True, "data": data}


def good_semantic():
    return ok([
        {"query": q, "kind": k, "expected": list(e) if e else None,
         "top_match": e[0] if e else "Title block font too small to read",
         "score": {"exact": 1.0, "paraphrase": 0.8, "unrelated": 0.3}[k], "expected_present": bool(e)}
        for q, k, e in rep.SEMANTIC_QUERIES])


def good_results():
    return {
        "infrastructure": ok({"postgres_comments": 6, "postgres_embedded": 6, "qdrant_comments_points": 6,
                              "qdrant_standards_points": 9}),
        "semantic_search": good_semantic(),
        "agentic_rag": ok({"verified": True, "evidence_status": "verified", "corpus_status": "illustrative_placeholder"}),
        "recommender": ok([{"comment": c, "status": "draft_requires_human_review", "requires_human_approval": True,
                            "auto_applied": False} for c in rep.RECOMMENDER_COMMENTS]),
    }


def test_all_passing_results_give_passing_verdict():
    gates = rep.evaluate_gates(good_results())
    assert {g["status"] for g in gates.values()} == {rep.PASS}
    v = rep.overall_verdict(gates)
    assert v["all_passed"] and v["text"] == "ALL LIVE CHECKS PASSED"
    assert "illustrative_placeholder" in gates["agentic_rag"]["reason"]   # PASS still labels the corpus


def test_missing_checks_are_errors_not_passes():
    gates = rep.evaluate_gates({})
    assert {g["status"] for g in gates.values()} == {rep.ERROR}
    assert not rep.overall_verdict(gates)["all_passed"]


@pytest.mark.parametrize("name,result,expected", [
    ("infrastructure", {"ran": False, "error": "OperationalError: connection refused"}, rep.ERROR),
    ("infrastructure", ok({"postgres_embedded": 0, "qdrant_comments_points": None, "qdrant_standards_points": 3}),
     rep.NO_DATA),
    ("agentic_rag", ok({"verified": False, "evidence_status": "faithfulness_failed"}), rep.FAIL),
    ("agentic_rag", ok({"not_configured": "OPENROUTER_API_KEY is not set"}), rep.NOT_CONFIGURED),
    ("recommender", ok([{"comment": "x", "status": "draft_requires_human_review", "requires_human_approval": True,
                         "auto_applied": True}]), rep.FAIL),
    ("recommender", ok([{"comment": "x", "status": "draft_unavailable", "requires_human_approval": True,
                         "auto_applied": False}]), rep.FAIL),
    ("recommender", ok([{"not_configured": "OPENROUTER_API_KEY is not set"}]), rep.NOT_CONFIGURED),
    ("recommender", ok([]), rep.NO_DATA),
])
def test_any_bad_gate_blocks_the_verdict(name, result, expected):
    results = good_results()
    results[name] = result
    gates = rep.evaluate_gates(results)
    assert gates[name]["status"] == expected
    v = rep.overall_verdict(gates)
    assert not v["all_passed"] and expected in v["text"]


def _semantic_with(**changes):
    res = good_semantic()
    for idx, fields in changes.items():
        res["data"][int(idx[1:])].update(fields)
    return res


def test_semantic_gate_no_data_wrong_hit_low_score_and_unrelated():
    assert rep.gate_semantic(_semantic_with(r1={"expected_present": False}))["status"] == rep.NO_DATA
    assert rep.gate_semantic(_semantic_with(r1={"top_match": "Add insulation"}))["status"] == rep.FAIL
    assert rep.gate_semantic(_semantic_with(r0={"score": 0.9}))["status"] == rep.FAIL          # exact < 0.95
    assert rep.gate_semantic(_semantic_with(r2={"score": 0.5}))["status"] == rep.FAIL          # below threshold
    assert rep.gate_semantic(_semantic_with(r3={"score": 0.85}))["status"] == rep.FAIL         # unrelated too high
    assert rep.gate_semantic(good_semantic())["status"] == rep.PASS


def test_demo_queries_match_the_current_demo_data():
    import demo_pipeline
    demo_texts = {t for _, t in demo_pipeline.HISTORICAL + demo_pipeline.NEW}
    for _, kind, expected in rep.SEMANTIC_QUERIES:
        if expected:
            assert set(expected) <= demo_texts
    assert set(rep.RECOMMENDER_COMMENTS) <= demo_texts and rep.RAG_COMMENT in demo_texts
    assert rep.DEMO_COLLECTIONS == demo_pipeline.DEMO_COLLECTIONS
    assert "hydraulic" not in Path(rep.__file__).read_text(encoding="utf-8")   # old, stale demo content


def _pdf_text(path: Path) -> str:
    return " ".join(p.get_text() for p in fitz.open(path))


def test_failed_run_writes_failing_report_from_any_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                       # not the repo folder
    def boom(ctx):
        raise ConnectionError("service unreachable")
    checks = [(n, d, boom) for n, d, _ in rep.CHECKS]
    out = tmp_path / "r.pdf"
    code = rep.main(["--out", str(out)], checks=checks)
    assert code == 1
    text = _pdf_text(out)
    assert "NOT ALL LIVE CHECKS PASSED" in text and "ALL LIVE CHECKS PASSED" not in text.replace("NOT ALL", "")
    assert "verified tonight" not in text and "per-project roles" not in text
    assert "the AI engine enforces no roles" in text.replace("\n", " ")
    import json
    j = json.loads(out.with_suffix(".json").read_text())
    assert j["verdict"]["all_passed"] is False
    assert Path(j["context"]["config_path"]) == ROOT / "config.yaml"


def test_passing_fake_checks_give_exit_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    good = good_results()
    checks = [(n, d, (lambda name: (lambda ctx: good[name]["data"]))(n)) for n, d, _ in rep.CHECKS]
    out = tmp_path / "r.pdf"
    assert rep.main(["--out", str(out)], checks=checks) == 0
    assert "Verdict: ALL LIVE CHECKS PASSED" in _pdf_text(out).replace("\n", " ")


def test_junit_summary_and_unreadable_file(tmp_path):
    x = tmp_path / "j.xml"
    x.write_text('<testsuites><testsuite name="pytest" tests="10" failures="1" errors="0" skipped="3" '
                 'timestamp="2026-10-17T10:00:00"/></testsuites>', encoding="utf-8")
    j = rep.read_junit(x)
    assert (j["passed"], j["failures"], j["skipped"]) == (6, 1, 3)
    assert "error" in rep.read_junit(tmp_path / "missing.xml")
    assert rep.read_junit(None) is None


def test_evaluation_without_real_dataset_says_real_metrics_unavailable(tmp_path):
    import json
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"datasets": [{"name": "synthetic", "kind": "synthetic",
                                            "metrics": {"extraction": {"status": "ok", "precision": 1.0, "n": 3}}}]}))
    out = tmp_path / "r.pdf"
    rep.main(["--out", str(out), "--evaluation", str(ev)],
             checks=[(n, d, lambda ctx: (_ for _ in ()).throw(RuntimeError("x"))) for n, d, _ in rep.CHECKS])
    text = _pdf_text(out).replace("\n", " ")
    assert "real-world accuracy is unavailable" in text and "synthetic" in text


@pytest.mark.skipif(not DSN, reason="CEMS_TEST_DATABASE_URL not set (real Postgres test)")
def test_infrastructure_check_on_real_demo_database(tmp_path, monkeypatch):
    """Runs the real read-only infrastructure check against the demo's Postgres database."""
    pytest.importorskip("qdrant_client")
    from urllib.parse import urlparse
    from qdrant_client import QdrantClient
    import demo_pipeline
    from database import db
    from vectordb import qdrant_client as vdb
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    server = QdrantClient(location=":memory:")
    monkeypatch.setattr(vdb, "_client", server)
    demo_pipeline.main(["--dsn", DSN, "--workdir", str(tmp_path / "demo"), "--recreate-demo-db", "--qdrant", "server"])
    u = urlparse(DSN)
    db.init_pool(host=u.hostname, port=u.port or 5432, dbname="cems_demo", user=u.username, password=u.password or "")
    try:
        ctx = rep.apply_target("demo")
        data = rep.check_infrastructure(ctx)
        assert data["postgres_comments"] == 6 and data["qdrant_comments_points"] == 6
        assert data["postgres_closed"] == 3 and data["postgres_documents"] == 2 and data["postgres_projects"] == 1
        assert rep.gate_infrastructure(ok(data))["status"] == rep.PASS
    finally:
        db._pool.closeall()
        db._pool = None

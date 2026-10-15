"""
Runs scripts/demo_pipeline.py end to end: real extractor CLI, real ingest, real PostgreSQL,
real Qdrant (in-memory), mock LLM + lexical hash embeddings (stand-ins, labelled in the output).
Skipped unless CEMS_TEST_DATABASE_URL is set and qdrant-client is installed.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

DSN = os.getenv("CEMS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="CEMS_TEST_DATABASE_URL not set (real Postgres test)")


def test_demo_produces_reviewable_drafts_with_honest_evidence(tmp_path, monkeypatch):
    pytest.importorskip("qdrant_client")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    import demo_pipeline
    report = demo_pipeline.main(["--dsn", DSN, "--workdir", str(tmp_path / "demo")])
    assert report["ingest"]["comments"] == 6 and not report["ingest"]["conflicts"]
    by_text = {c["comment"]: c for c in report["comments"]}
    assert len(by_text) == 3
    for c in report["comments"]:
        assert c["status"] == "draft_requires_human_review"
        assert c["requires_human_approval"] is True and c["auto_applied"] is False
        assert all("DWG200" not in h["comment_uid"] for h in c["historical_examples"])   # never itself/own drawing
    weld = next(c for t, c in by_text.items() if t.startswith("Fillet weld"))
    assert weld["basis"] == "both" and weld["standards_evidence_status"] == "verified"
    assert weld["standards_evidence"] == ["AWS D1.1 Clause 2.4"]
    assert weld["corpus_status"] == "illustrative_placeholder"
    assert any("not authoritative" in u for u in weld["uncertainty"])
    insulation = next(c for t, c in by_text.items() if t.startswith("Add insulation"))
    assert insulation["basis"] == "generic" and insulation["historical_examples"] == []
    assert (tmp_path / "demo" / "demo_report.json").exists()

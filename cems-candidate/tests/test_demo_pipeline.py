"""
Runs scripts/demo_pipeline.py end to end on the FINAL schema: real extractor CLI, real loader, real
PostgreSQL, real Qdrant (in-memory), mock LLM + lexical hash embeddings (stand-ins, labelled).
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
    report = demo_pipeline.main(["--dsn", DSN, "--workdir", str(tmp_path / "demo"), "--recreate-demo-db"])
    assert report["ingest"]["comments"] == 6 and not report["ingest"]["conflicts"]
    assert report["standards"]["upserted"] == 7
    by_text = {c["comment"]: c for c in report["comments"]}
    assert len(by_text) == 3
    for c in report["comments"]:
        assert c["status"] == "draft_requires_human_review"
        assert c["requires_human_approval"] is True and c["auto_applied"] is False
        assert c["stored_status"] == "open" and c["stored_resolution_text"] is None    # a draft resolves nothing
        assert c["saved"] is True and c["stored_ai_suggested_resolution"]
        assert all("DWG200" not in h["comment_id"] for h in c["historical_examples"])   # never itself/own drawing
    weld = next(c for t, c in by_text.items() if t.startswith("Fillet weld"))
    assert weld["basis"] == "both" and weld["standards_evidence_status"] == "verified"
    assert weld["standards_evidence"] == ["AWS D1.1 Clause 2.4"]
    assert weld["corpus_status"] == "illustrative_placeholder"
    assert weld["stored_ai_suggested_resolution"].endswith("Referenced standards: AWS D1.1 Clause 2.4")
    assert float(weld["stored_ai_confidence_percent"]) == 75
    assert weld["trace"]["cited_chunk_ids"] and weld["trace"]["subqueries"]
    assert any("not authoritative" in u for u in weld["uncertainty"])
    insulation = next(c for t, c in by_text.items() if t.startswith("Add insulation"))
    assert insulation["basis"] == "generic" and insulation["historical_examples"] == []
    assert (tmp_path / "demo" / "demo_report.json").exists()


def test_demo_refuses_to_drop_an_existing_demo_db_or_cems():
    import demo_pipeline
    conn, _ = demo_pipeline.create_database(DSN, "cems_demo", recreate=True)
    conn.close()
    with pytest.raises(demo_pipeline.DemoDatabaseExists):
        demo_pipeline.create_database(DSN, "cems_demo")
    for name in ("cems", "postgres"):
        with pytest.raises(ValueError, match="refusing"):
            demo_pipeline.create_database(DSN, name, recreate=True)


def test_demo_server_mode_never_touches_team_collections(tmp_path, monkeypatch):
    """Server mode used to delete 'comments' and 'standards_chunks'. Simulate a server holding team
    data (qdrant local mode stands in for the server) and check it survives a demo run."""
    pytest.importorskip("qdrant_client")
    from qdrant_client import QdrantClient, models
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from vectordb import qdrant_client as vdb
    server = QdrantClient(location=":memory:")
    for name in ("comments", "standards_chunks"):
        server.create_collection(name, vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE))
    server.upsert("comments", points=[models.PointStruct(id=1, vector=[0.1] * 768, payload={"team": "data"})])
    monkeypatch.setattr(vdb, "_client", server)
    monkeypatch.setattr(vdb, "COMMENTS_COLLECTION", "comments")
    monkeypatch.setattr(vdb, "STANDARDS_COLLECTION", "standards_chunks")
    import demo_pipeline
    report = demo_pipeline.main(["--dsn", DSN, "--workdir", str(tmp_path / "demo"), "--recreate-demo-db",
                                 "--qdrant", "server"])
    assert report["ingest"]["comments"] == 6
    names = {c.name for c in server.get_collections().collections}
    assert {"comments", "standards_chunks", *demo_pipeline.DEMO_COLLECTIONS} <= names
    assert server.count("comments").count == 1                    # team data untouched
    assert server.count("cems_demo_comments").count == 6

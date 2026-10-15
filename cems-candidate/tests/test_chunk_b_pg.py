"""
Chunk B database behaviour on a REAL PostgreSQL (throw-away database, schema.sql applied).
Skipped unless CEMS_TEST_DATABASE_URL is set; see tests/test_ingest_pg.py.
"""
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ingest_pg import DSN, pg, q  # noqa: E402,F401  (pg is a fixture)

pytestmark = pytest.mark.skipif(not DSN, reason="CEMS_TEST_DATABASE_URL not set (real Postgres test)")


def test_standards_seed_is_idempotent(pg):
    ingest, db, conn = pg
    doc = db.get_or_create_standards_document("AWS D1.1 (illustrative excerpt)", "AWS D1.1", "Welding")
    chunks = [{"chunk_index": i, "chunk_text": t, "section_reference": s}
              for i, (s, t) in enumerate([("Clause 2.4", "Fillet weld size..."), ("Clause 7.2.1", "Visual inspection..."),
                                          ("Table 2.1", "Weld symbols...")])]
    assert db.insert_standards_chunks_bulk(doc, chunks) == 3
    assert db.insert_standards_chunks_bulk(doc, chunks) == 0           # second seed run adds nothing
    assert q(conn, "SELECT count(*) FROM standards_chunks")[0][0] == 3


def test_history_is_human_only_newest_first_and_suggestions_never_resolve(pg):
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A, texts=["Weld size wrong", "Font too small"])), "t")
    c1, c2 = [r[0] for r in q(conn, "SELECT id::text FROM comments ORDER BY sr_no")]

    db.insert_resolution(c1, "OLD: weld resized to 6 mm", resolved_by="eng-a", source="manual")
    time.sleep(0.01)
    db.insert_resolution(c1, "NEW: weld resized to 8 mm", resolved_by="eng-b", source="manual")
    time.sleep(0.01)
    db.insert_resolution(c1, "AI draft: resize weld", source="ai_suggested")
    db.insert_resolution(c2, "AI draft: enlarge font", source="ai_suggested")

    hist = db.get_resolution_history_for([c1, c2])
    assert [h["resolution_text"] for h in hist] == ["NEW: weld resized to 8 mm", "OLD: weld resized to 6 mm"]
    assert all(h["source"] != "ai_suggested" for h in hist)
    status = dict(q(conn, "SELECT id::text, status::text FROM comments"))
    assert status[c1] == "resolved"                  # by the human resolutions
    assert status[c2] == "open"                      # an AI suggestion alone never resolves


def test_comment_context_returns_scope_ids(pg):
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A)), "t")
    cid, rev = q(conn, "SELECT id::text, revision_id::text FROM comments LIMIT 1")[0]
    ctx = db.get_comment_context(cid)
    assert ctx["revision_id"] == rev and ctx["project_id"] and ctx["document_id"]
    assert db.get_comment_context("00000000-0000-0000-0000-000000000000") is None


def test_rag_trace_is_actually_stored(pg):
    """Before the ::uuid[] cast every trace insert failed (and the failure was only logged)."""
    import uuid as _uuid
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A)), "t")
    cid = q(conn, "SELECT id::text FROM comments LIMIT 1")[0][0]
    chunk_ids = [str(_uuid.uuid4()), str(_uuid.uuid4())]
    db.log_rag_trace(comment_id=cid, original_query="weld?", decomposed_subqueries=["weld size?"],
                     retrieval_hops=[{"hop": 1, "query": "weld size?", "chunks_retrieved": 2, "error": None}],
                     faithfulness_passed=True, faithfulness_notes="[verified] ok", final_answer="a",
                     cited_chunk_ids=chunk_ids)
    stored = q(conn, "SELECT cited_chunk_ids::text[], faithfulness_passed FROM rag_query_traces")
    assert len(stored) == 1 and sorted(stored[0][0]) == sorted(chunk_ids) and stored[0][1] is True

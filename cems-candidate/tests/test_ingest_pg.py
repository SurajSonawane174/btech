"""
The FINAL schema on a REAL PostgreSQL: database/schema.sql is applied to a throw-away database and
database/db.py, ingest.py and vectordb/comment_sync.py run unmodified (Qdrant in-memory, embeddings
stubbed). Skipped unless CEMS_TEST_DATABASE_URL points at a server where the user may CREATE DATABASE:
    $env:CEMS_TEST_DATABASE_URL = "postgresql://cems:cems_dev_password@localhost:5432/postgres"
The test creates and drops its own database (cems_test_<random>); it never touches 'cems'.
"""
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

DSN = os.getenv("CEMS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="CEMS_TEST_DATABASE_URL not set (real Postgres test)")


@pytest.fixture
def pg():
    import psycopg2
    from test_ingest import import_ingest_with_stubbed_vectors
    u = urlparse(DSN)
    name = f"cems_test_{uuid.uuid4().hex[:10]}"
    admin = psycopg2.connect(DSN)
    admin.autocommit = True
    admin.cursor().execute(f'CREATE DATABASE "{name}"')
    try:
        conn = psycopg2.connect(DSN.rsplit("/", 1)[0] + "/" + name if u.path else DSN + "/" + name)
        conn.autocommit = True
        conn.cursor().execute((ROOT / "database/schema.sql").read_text(encoding="utf-8"))
        ingest, calls = import_ingest_with_stubbed_vectors()
        from database import db
        if db._pool is not None:
            db._pool.closeall()
        db.init_pool(host=u.hostname, port=u.port or 5432, dbname=name, user=u.username, password=u.password or "")
        yield ingest, db, conn
        db._pool.closeall()
        db._pool = None
        conn.close()
    finally:
        admin.cursor().execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin.close()


def q(conn, sql, *args):
    cur = conn.cursor()
    cur.execute(sql, args)
    return cur.fetchall()


FORM = dict(praj_project_number="P-1001", supplier_name="ACME Fabricators", supplier_po_number="PO-1")


def ingest_rows(ingest, data, **kw):
    form = dict(FORM)
    form.update({k: kw.pop(k) for k in list(kw) if k in form})
    return ingest.ingest_dataframe(pd.DataFrame(data), "t", **form, **kw)


def test_schema_is_exactly_the_final_three_tables(pg):
    _, _, conn = pg
    tables = sorted(r[0] for r in q(conn, "SELECT table_name FROM information_schema.tables "
                                          "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"))
    assert tables == ["comments", "documents", "users"]
    assert q(conn, "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
                   "WHERE n.nspname = 'public' AND t.typtype = 'e'")[0][0] == 0          # no ENUM types
    assert q(conn, "SELECT count(*) FROM pg_extension WHERE extname = 'uuid-ossp'")[0][0] == 0
    cols = dict(q(conn, "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'comments'"))
    for c in ("embedded", "ai_suggested_resolution", "ai_confidence_percent", "resolution_text", "resolved_at"):
        assert c in cols
    assert cols["id"] == "bigint" and cols["document_id"] == "bigint" and cols["comment_datetime"].startswith("timestamp")
    defs = dict(q(conn, "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
                        "WHERE conrelid = 'documents'::regclass AND contype = 'u'"))
    assert defs == {"unique_doc_revision": "UNIQUE (praj_project_number, praj_document_number, "
                                           "praj_revision_number, supplier_name, supplier_po_number)"}


def test_counts_idempotency_conflicts_and_revisions_on_real_postgres(pg):
    from test_ingest import rows, SHA_A, SHA_B
    ingest, db, conn = pg
    t1 = ingest_rows(ingest, rows(SHA_A, rev="RA"))
    assert (t1["comments"], t1["already_present"]) == (2, 0)
    t2 = ingest_rows(ingest, rows(SHA_A, rev="RA"))
    assert (t2["comments"], t2["already_present"]) == (0, 2)                    # idempotent
    t3 = ingest_rows(ingest, rows(SHA_B, rev="RA"))
    assert t3["comments"] == 0 and len(t3["conflicts"]) == 1                    # other file, same revision
    t4 = ingest_rows(ingest, rows(SHA_B, rev="RB"))
    assert t4["comments"] == 2                                                  # Rev B = a second row
    assert q(conn, "SELECT praj_document_number, praj_revision_number FROM documents ORDER BY id") == \
        [("DWG101", "RA"), ("DWG101", "RB")]
    assert db.get_document_revisions("P-1001", "DWG101")[0]["praj_revision_number"] in ("RA", "RB")
    assert len(db.get_document_revisions("P-1001", "DWG101")) == 2
    assert q(conn, "SELECT count(*) FROM comments")[0][0] == 4


def test_same_pdf_under_another_supplier_is_reported_not_inserted(pg):
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    ingest_rows(ingest, rows(SHA_A))
    t = ingest_rows(ingest, rows(SHA_A), supplier_name="Other Supplier")
    assert t["comments"] == 0 and len(t["conflicts"]) == 1
    assert q(conn, "SELECT count(*) FROM documents")[0][0] == 1                 # no empty document row


def test_stored_values_follow_the_final_columns(pg):
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    data = rows(SHA_A, rev="NA", rev_src="unresolved", texts=["NA", "Weld size wrong"])
    data[1]["date_of_comment"], data[1]["time_of_comment"] = "12-09-2026", "14:25"     # ambiguous OCR date
    data[0]["extraction_confidence_percent"] = ""
    t = ingest_rows(ingest, data)
    assert t["comments"] == 2 and t["datetime_not_stored"] == 1
    doc = q(conn, "SELECT praj_project_number, praj_revision_number, supplier_name, supplier_po_number, "
                  "customer_document_number, customer_revision, is_released FROM documents")
    assert doc == [("P-1001", "NA", "ACME Fabricators", "PO-1", None, None, False)]
    got = q(conn, "SELECT actual_extracted_comment, page_sheet, comment_datetime::text, is_client_comment, "
                  "is_handwritten, extraction_confidence_percent, comment_category, status, embedded, "
                  "ai_suggested_resolution, resolution_text, resolved_at FROM comments ORDER BY id")
    assert got[0] == ("NA", "1", "2026-03-12 10:15:00", True, False, None, "technical", "open", False,
                      None, None, None)
    assert got[1][2] is None


def test_ai_suggestion_resolve_and_reopen(pg):
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    ingest_rows(ingest, rows(SHA_A))
    cid = q(conn, "SELECT id FROM comments ORDER BY id LIMIT 1")[0][0]
    assert db.save_ai_suggestion(cid, "Resize the weld.", 75) is True
    assert q(conn, "SELECT status, resolution_text, resolved_at FROM comments WHERE id = %s", cid)[0] == \
        ("open", None, None)                                                    # a draft resolves nothing
    with pytest.raises(ValueError):
        db.resolve_comment(cid, "   ")
    row = db.resolve_comment(cid, "Weld resized to 8 mm.")
    assert row["status"] == "closed" and row["resolution_text"] == "Weld resized to 8 mm." and row["resolved_at"]
    assert row["ai_suggested_resolution"] == "Resize the weld." and float(row["ai_confidence_percent"]) == 75
    row = db.reopen_comment(cid)
    assert row["status"] == "open" and row["resolved_at"] is None and row["resolution_text"] == "Weld resized to 8 mm."
    assert db.resolve_comment(999999, "x") is None and db.reopen_comment(999999) is None
    assert db.save_ai_suggestion(999999, "x", 1) is False
    ctx = db.get_comment_context(cid)
    assert ctx["praj_project_number"] == "P-1001" and ctx["supplier_po_number"] == "PO-1"


def _real_sync(monkeypatch, fail_on=None):
    """Real comment_sync + real qdrant_client module on an in-memory Qdrant, stub embeddings."""
    pytest.importorskip("qdrant_client")
    import importlib
    for k in ("vectordb.comment_sync", "vectordb.qdrant_client", "vectordb.embedder"):
        sys.modules.pop(k, None)
    import vectordb
    for a in ("comment_sync", "qdrant_client", "embedder"):
        if hasattr(vectordb, a):
            delattr(vectordb, a)
    cs = importlib.import_module("vectordb.comment_sync")
    from qdrant_client import QdrantClient
    monkeypatch.setattr(cs.vdb, "_client", QdrantClient(location=":memory:"))

    def embed(text):
        if fail_on and fail_on in text:
            raise ConnectionError("ollama down")
        v = [0.0] * 768
        v[sum(map(ord, text)) % 768] = 1.0
        v[0] += 0.5
        return v
    monkeypatch.setattr(cs.embedder, "embed_text", embed)
    return cs


def test_embedding_sync_and_payload_lifecycle(pg, monkeypatch):
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    ingest_rows(ingest, rows(SHA_A, texts=["Weld size wrong", "Font too small", "FAIL me"]), embed=False)
    cs = _real_sync(monkeypatch, fail_on="FAIL")
    r = cs.sync_embeddings()
    assert (r["embedded"], r["failed"]) == (2, 1)
    assert q(conn, "SELECT actual_extracted_comment, embedded FROM comments ORDER BY id") == \
        [("Weld size wrong", True), ("Font too small", True), ("FAIL me", False)]
    ids = [x[0] for x in q(conn, "SELECT id FROM comments ORDER BY id")]
    point = cs.vdb.get_client().retrieve(cs.vdb.COMMENTS_COLLECTION, ids=[ids[0]])[0]
    assert point.id == ids[0] and point.payload["praj_project_number"] == "P-1001"
    assert point.payload["document_id"] == q(conn, "SELECT id FROM documents")[0][0]
    assert point.payload["status"] == "open" and "resolution_text" not in point.payload

    out = cs.resolve_comment(ids[0], "Weld resized to 8 mm.")
    assert out["warning"] is None and out["comment"]["status"] == "closed"
    hits = cs.find_similar(text="Weld size wrong", only_resolved=True, score_threshold=0.0)["results"]
    assert [(h["id"], h["resolution_text"]) for h in hits] == [(ids[0], "Weld resized to 8 mm.")]
    by_id = cs.find_similar(comment_pk=ids[1], score_threshold=0.0)["results"]
    assert ids[1] not in [h["id"] for h in by_id]                                 # never itself

    cs.reopen_comment(ids[0])
    assert cs.find_similar(text="Weld size wrong", only_resolved=True, score_threshold=0.0)["results"] == []

    monkeypatch.setattr(cs.vdb, "update_comment_payload", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    out = cs.resolve_comment(ids[1], "Text height set to 3.5 mm.")
    assert "re-sync" in out["warning"]
    assert q(conn, "SELECT status, embedded FROM comments WHERE id = %s", ids[1])[0] == ("closed", False)
    with pytest.raises(LookupError):
        cs.resolve_comment(999999, "x")


def test_rebuild_recreates_collection_and_reembeds_everything(pg, monkeypatch):
    from test_ingest import rows, SHA_A
    ingest, db, conn = pg
    ingest_rows(ingest, rows(SHA_A), embed=False)
    cs = _real_sync(monkeypatch)
    cs.sync_embeddings()
    r = cs.rebuild_comment_vectors()
    assert (r["reset_rows"], r["embedded"]) == (2, 2)
    assert cs.vdb.get_client().count(cs.vdb.COMMENTS_COLLECTION).count == 2


def test_standards_seed_writes_qdrant_only_and_is_idempotent(pg, monkeypatch):
    _, _, conn = pg
    cs = _real_sync(monkeypatch)
    sys.modules.pop("standards_corpus.seed_standards", None)
    from standards_corpus import seed_standards as seed
    monkeypatch.setattr(seed, "vdb", cs.vdb)
    monkeypatch.setattr(seed.embedder, "embed_text", cs.embedder.embed_text)
    r1, r2 = seed.seed(), seed.seed()
    assert r1["upserted"] == r2["upserted"] == 7 and not r1["failed"]
    assert cs.vdb.get_client().count(cs.vdb.STANDARDS_COLLECTION).count == 7     # same ids, no duplicates
    p = cs.vdb.get_client().scroll(cs.vdb.STANDARDS_COLLECTION, limit=1)[0][0].payload
    assert {"code_reference", "section_reference", "page_number", "chunk_text"} <= set(p)
    assert p["corpus_status"] == "illustrative_placeholder"
    assert q(conn, "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")[0][0] == 3

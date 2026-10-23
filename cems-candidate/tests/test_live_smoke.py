"""scripts/live_smoke.py: per-check statuses, no mock fallback, no secrets, non-destructive."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_smoke as S  # noqa: E402
from test_ingest_pg import pg  # noqa: E402,F401  (fixture: throw-away database with schema.sql)

DSN = os.getenv("CEMS_TEST_DATABASE_URL")


# ------------------------------------------------------------------ Qdrant

def test_qdrant_round_trip_leaves_existing_collections_alone():
    qc = pytest.importorskip("qdrant_client")
    from qdrant_client import models
    client = qc.QdrantClient(location=":memory:")
    client.create_collection("comments", vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE))
    client.upsert("comments", points=[models.PointStruct(id=7, vector=[0, 0, 1, 0], payload={"team": 1})])
    r = S.check_qdrant(client)
    assert r["status"] == S.PASS, r
    assert [c.name for c in client.get_collections().collections] == ["comments"]
    assert client.count("comments").count == 1


def test_qdrant_unreachable_is_fail():
    class Down:
        def get_collections(self):
            raise ConnectionError("refused")
    r = S.check_qdrant(Down())
    assert r["status"] == S.FAIL and "refused" in r["detail"]


def test_qdrant_failure_after_create_still_deletes_only_its_collection():
    qc = pytest.importorskip("qdrant_client")
    real = qc.QdrantClient(location=":memory:")
    deleted = []

    class Flaky:
        def get_collections(self):
            return real.get_collections()

        def create_collection(self, *a, **k):
            return real.create_collection(*a, **k)

        def upsert(self, *a, **k):
            raise RuntimeError("write rejected")

        def delete_collection(self, name):
            deleted.append(name)
            return real.delete_collection(name)
    r = S.check_qdrant(Flaky())
    assert r["status"] == S.FAIL and "write rejected" in r["detail"]
    assert len(deleted) == 1 and deleted[0].startswith(S.TEMP_PREFIX)
    assert real.get_collections().collections == []


# ------------------------------------------------------------------ embedding

def fake_embedder(models=("nomic-embed-text:latest",), dim=768, list_error=None, embed_error=None):
    def _list():
        if list_error:
            raise list_error
        return {"models": [{"name": m} for m in models]}

    def embed_text(t):
        if embed_error:
            raise embed_error
        return [1.0 if i == len(t) % dim else 0.1 for i in range(dim)]
    from vectordb import embedder as real
    return SimpleNamespace(OLLAMA_HOST="http://localhost:11434", EMBED_MODEL="nomic-embed-text",
                           _get_client=lambda: SimpleNamespace(list=_list), _model_names=real._model_names,
                           embed_text=embed_text)


def test_embedding_statuses():
    assert S.check_embedding(fake_embedder())["status"] == S.PASS
    r = S.check_embedding(fake_embedder(models=("llama3",)))
    assert r["status"] == S.FAIL and "ollama pull" in r["detail"]
    assert S.check_embedding(fake_embedder(list_error=ConnectionError("down")))["status"] == S.FAIL
    assert S.check_embedding(fake_embedder(embed_error=ValueError("returned 384 dims")))["status"] == S.FAIL


# ------------------------------------------------------------------ LLM

class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def __call__(self, cfg):                 # used as make_client
        return self

    def chat_json(self, system, user):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


def test_llm_not_configured_makes_no_call(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    import comment_extractor  # noqa: F401  (loads .env first, then we remove the key again)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    fake = FakeLLM({"ok": True, "sum": 5})
    r = S.check_llm(make_client=fake)
    assert r["status"] == S.NOT_CONFIGURED and fake.calls == 0


@pytest.mark.parametrize("reply,error,expected", [
    ({"ok": True, "sum": 5}, None, S.PASS),
    ({"ok": "maybe", "sum": 5}, None, S.FAIL),          # not a parseable boolean -> fails closed
    ({"ok": True, "sum": 6}, None, S.FAIL),
    (["ok"], None, S.FAIL),
    (None, TimeoutError("timed out"), S.FAIL),
])
def test_llm_reply_validation(monkeypatch, reply, error, expected):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-not-real")
    r = S.check_llm(make_client=FakeLLM(reply, error))
    assert r["status"] == expected
    assert "sk-test-not-real" not in r["detail"]


# ------------------------------------------------------------------ main / secrets

def test_exit_codes():
    assert S.exit_code({"a": {"status": S.PASS}}) == 0
    assert S.exit_code({"a": {"status": S.PASS}, "b": {"status": S.SKIPPED}}) == 3
    assert S.exit_code({"a": {"status": S.NOT_CONFIGURED}}) == 3
    assert S.exit_code({"a": {"status": S.PASS}, "b": {"status": S.FAIL}}) == 1
    assert S.exit_code({}) == 3


def test_crashing_check_is_a_failure_and_results_are_written(tmp_path, capsys):
    def crash():
        raise RuntimeError("bug")
    out = tmp_path / "s.json"
    code = S.main(["--json", str(out)], checks={"postgres": lambda: S.result(S.PASS, "ok"), "qdrant": crash})
    assert code == 1 and '"FAIL"' in out.read_text()
    assert "check crashed" in capsys.readouterr().out


def test_postgres_password_never_printed(monkeypatch, capsys):
    monkeypatch.setenv("POSTGRES_PASSWORD", "s3cret-pw")

    def connect(**kw):
        raise RuntimeError(f"password authentication failed (password={kw['password']})")
    r = S.check_postgres(connect=connect)
    assert r["status"] == S.FAIL and "s3cret-pw" not in r["detail"] and "***" in r["detail"]
    S.main([], checks={"postgres": lambda: S.check_postgres(connect=connect)})
    assert "s3cret-pw" not in capsys.readouterr().out


def test_temp_db_skipped_unless_requested_and_not_configured_without_dsn(monkeypatch):
    assert S.check_postgres_temp_db(False)["status"] == S.SKIPPED
    monkeypatch.delenv("CEMS_TEST_DATABASE_URL", raising=False)
    assert S.check_postgres_temp_db(True)["status"] == S.NOT_CONFIGURED


# ------------------------------------------------------------------ real PostgreSQL

pg_only = pytest.mark.skipif(not DSN, reason="CEMS_TEST_DATABASE_URL not set (real Postgres test)")


def _databases():
    import psycopg2
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("SELECT datname FROM pg_database")
    names = {r[0] for r in cur.fetchall()}
    conn.close()
    return names


@pg_only
def test_temp_db_round_trip_creates_and_drops_only_its_own_database():
    before = _databases()
    r = S.check_postgres_temp_db(True, DSN)
    assert r["status"] == S.PASS, r
    assert _databases() == before                                   # nothing left behind, nothing removed
    assert urlparse(DSN).password not in r["detail"]


@pg_only
def test_postgres_check_reads_schema_of_configured_database(pg, monkeypatch):
    ingest, db, conn = pg
    u = urlparse(DSN)
    name = conn.get_dsn_parameters()["dbname"]
    for k, v in {"POSTGRES_HOST": u.hostname, "POSTGRES_PORT": str(u.port or 5432), "POSTGRES_DB": name,
                 "POSTGRES_USER": u.username, "POSTGRES_PASSWORD": u.password or ""}.items():
        monkeypatch.setenv(k, v)
    r = S.check_postgres()
    assert r["status"] == S.PASS, r
    conn.cursor().execute("DROP TABLE rag_query_traces")
    r = S.check_postgres()
    assert r["status"] == S.FAIL and "rag_query_traces" in r["detail"]

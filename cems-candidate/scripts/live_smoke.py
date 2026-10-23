"""
scripts/live_smoke.py -- check the REAL services the AI engine depends on, one by one.

    python scripts/live_smoke.py [--pg-temp-db] [--only postgres,qdrant,embedding,llm] [--json out.json]

Checks and what each does:
  postgres            connect with POSTGRES_HOST/PORT/DB/USER/PASSWORD (same defaults as
                      database/db.py), SELECT version(), check that the CEMS tables exist. Read-only.
  postgres_temp_db    only with --pg-temp-db and CEMS_TEST_DATABASE_URL set: create a database named
                      cems_smoke_<random>, apply database/schema.sql, insert + read back one row, drop
                      THAT database. No other database is created, changed or dropped. Without it,
                      the check is SKIPPED and the Postgres integration path stays unverified here.
  qdrant              connect with QDRANT_HOST/PORT, list collections, then create a collection named
                      cems_smoke_<random>, upsert/search two points and delete only that collection.
                      Existing collections are never written or deleted (checked before/after).
  embedding           Ollama at OLLAMA_HOST: model OLLAMA_EMBED_MODEL listed, one embedding call,
                      dimension == EMBEDDING_DIM. Two cosine scores are printed for information only.
  llm                 if the API key named in config.yaml (llm.api_key_env) is set: one chat_json call
                      that must return {"ok": true, "sum": 5}. Otherwise NOT_CONFIGURED; nothing is called.

Each check reports PASS, FAIL, SKIPPED or NOT_CONFIGURED. There is no fallback to a mock: a check
that cannot reach its real service fails or is skipped, and is reported that way.
Secrets are never printed: connection targets are shown as host:port/database (user) only.

Exit code: 0 when every check run is PASS and none was skipped or not configured; 1 when any
check FAILED; 3 otherwise (nothing failed, but something was not verified).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PASS, FAIL, SKIPPED, NOT_CONFIGURED = "PASS", "FAIL", "SKIPPED", "NOT_CONFIGURED"
TEMP_PREFIX = "cems_smoke_"
CEMS_TABLES = ("projects", "documents", "revisions", "comments", "resolutions", "standards_chunks",
               "rag_query_traces")


def result(status: str, detail: str, **extra) -> Dict:
    return {"status": status, "detail": detail, **extra}


def _err(e: Exception) -> str:
    """Exception text with anything that looks like a password removed."""
    msg = f"{type(e).__name__}: {e}".strip().replace("\n", " ")
    pw = os.getenv("POSTGRES_PASSWORD")
    for secret in filter(None, [pw, _dsn_password(os.getenv("CEMS_TEST_DATABASE_URL"))]):
        msg = msg.replace(secret, "***")
    return msg[:300]


def _dsn_password(dsn: Optional[str]) -> Optional[str]:
    try:
        return urlparse(dsn).password if dsn else None
    except Exception:
        return None


def pg_params() -> Dict:
    return {"host": os.getenv("POSTGRES_HOST", "localhost"), "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "dbname": os.getenv("POSTGRES_DB", "cems"), "user": os.getenv("POSTGRES_USER", "cems"),
            "password": os.getenv("POSTGRES_PASSWORD", "cems_dev_password")}


def describe_pg(p: Dict) -> str:
    return f"{p['host']}:{p['port']}/{p['dbname']} (user {p['user']})"


# ------------------------------------------------------------------ checks

def check_postgres(connect=None) -> Dict:
    p = pg_params()
    target = describe_pg(p)
    try:
        import psycopg2
        conn = (connect or psycopg2.connect)(connect_timeout=5, **p)
    except Exception as e:
        return result(FAIL, f"cannot connect to {target}: {_err(e)}", target=target)
    try:
        cur = conn.cursor()
        cur.execute("SELECT version()")
        version = cur.fetchone()[0].split(",")[0]
        cur.execute("SELECT t FROM unnest(%s::text[]) AS t WHERE to_regclass('public.' || t) IS NULL",
                    (list(CEMS_TABLES),))
        missing = [r[0] for r in cur.fetchall()]
        conn.rollback()
    except Exception as e:
        return result(FAIL, f"connected to {target} but query failed: {_err(e)}", target=target)
    finally:
        conn.close()
    if missing:
        return result(FAIL, f"{target}: {version}; schema incomplete, missing tables: {', '.join(missing)}",
                      target=target)
    return result(PASS, f"{target}: {version}; CEMS tables present (read-only check)", target=target)


def check_postgres_temp_db(enabled: bool, dsn: Optional[str] = None) -> Dict:
    if not enabled:
        return result(SKIPPED, "not requested (--pg-temp-db); Postgres integration path unverified by this run")
    dsn = dsn or os.getenv("CEMS_TEST_DATABASE_URL")
    if not dsn:
        return result(NOT_CONFIGURED, "CEMS_TEST_DATABASE_URL is not set; integration path unverified")
    import psycopg2
    u = urlparse(dsn)
    target = f"{u.hostname}:{u.port or 5432}{u.path or ''} (user {u.username})"
    name = f"{TEMP_PREFIX}{uuid.uuid4().hex[:10]}"
    assert name.startswith(TEMP_PREFIX)
    try:
        admin = psycopg2.connect(dsn, connect_timeout=5)
        admin.autocommit = True
    except Exception as e:
        return result(FAIL, f"cannot connect to {target}: {_err(e)}")
    created = False
    try:
        try:
            admin.cursor().execute(f'CREATE DATABASE "{name}"')
            created = True
        except Exception as e:
            return result(SKIPPED, f"cannot create a temporary database on {target} ({_err(e)}); "
                                   f"connectivity only, integration path unverified")
        conn = psycopg2.connect(host=u.hostname, port=u.port or 5432, dbname=name, user=u.username,
                                password=u.password or "", connect_timeout=5)
        try:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute((ROOT / "database/schema.sql").read_text(encoding="utf-8"))
            cur.execute("INSERT INTO projects (project_code, project_name) VALUES ('SMOKE', 'smoke test') RETURNING id::text")
            pid = cur.fetchone()[0]
            cur.execute("SELECT project_code FROM projects WHERE id = %s", (pid,))
            ok = cur.fetchone()[0] == "SMOKE"
        finally:
            conn.close()
        if not ok:
            return result(FAIL, f"temporary database {name}: row did not read back")
        return result(PASS, f"temporary database {name} on {target}: schema applied, insert/select ok, dropped")
    except Exception as e:
        return result(FAIL, f"temporary database {name}: {_err(e)}")
    finally:
        if created:
            try:
                admin.cursor().execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
            except Exception as e:
                print(f"WARNING: could not drop temporary database {name}: {_err(e)}")
        admin.close()


def check_qdrant(client=None) -> Dict:
    host, port = os.getenv("QDRANT_HOST", "localhost"), int(os.getenv("QDRANT_PORT", "6333"))
    target = f"{host}:{port}"
    try:
        from qdrant_client import QdrantClient, models
        client = client or QdrantClient(host=host, port=port, timeout=10)
        before = {c.name for c in client.get_collections().collections}
    except Exception as e:
        return result(FAIL, f"cannot reach Qdrant at {target}: {_err(e)}", target=target)
    name = f"{TEMP_PREFIX}{uuid.uuid4().hex[:10]}"
    if name in before:                                   # practically impossible; never reuse a name
        return result(FAIL, f"temporary collection name {name} already exists; not touching it")
    created = False
    try:
        client.create_collection(name, vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE))
        created = True
        client.upsert(name, points=[models.PointStruct(id=1, vector=[1, 0, 0, 0], payload={"t": "a"}),
                                    models.PointStruct(id=2, vector=[0, 1, 0, 0], payload={"t": "b"})], wait=True)
        hits = client.query_points(name, query=[0.9, 0.1, 0, 0], limit=1).points
        ok = bool(hits) and hits[0].id == 1
    except Exception as e:
        return result(FAIL, f"round trip on {target} failed: {_err(e)}", target=target)
    finally:
        if created:
            try:
                client.delete_collection(name)
            except Exception as e:
                print(f"WARNING: could not delete temporary collection {name}: {_err(e)}")
    after = {c.name for c in client.get_collections().collections}
    if after != before:
        return result(FAIL, f"collection set changed during the check: added {sorted(after - before)}, "
                            f"removed {sorted(before - after)}", target=target)
    if not ok:
        return result(FAIL, f"{target}: nearest-neighbour search returned the wrong point", target=target)
    return result(PASS, f"{target}: {len(before)} existing collection(s) untouched; temporary collection "
                        f"create/upsert/search/delete ok", target=target, collections=sorted(before))


def _cos(a, b) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def check_embedding(emb=None) -> Dict:
    if emb is None:
        from vectordb import embedder as emb
    target = f"{emb.OLLAMA_HOST} model {emb.EMBED_MODEL}"
    try:
        names = emb._model_names(emb._get_client().list())
    except Exception as e:
        return result(FAIL, f"Ollama client unavailable or {emb.OLLAMA_HOST} unreachable: {_err(e)}", target=target)
    base = emb.EMBED_MODEL.split(":")[0]
    if not any(n == emb.EMBED_MODEL or n.split(":")[0] == base for n in names):
        return result(FAIL, f"model {emb.EMBED_MODEL} not pulled (ollama pull {emb.EMBED_MODEL})", target=target)
    try:
        a = emb.embed_text("Verify fillet weld size per AWS D1.1 for the support bracket")
        b = emb.embed_text("Check the support bracket fillet weld dimension against AWS D1.1")
        c = emb.embed_text("Provide a lifting lug on the pump base frame")
    except Exception as e:
        return result(FAIL, f"embedding call failed: {_err(e)}", target=target)
    info = {"cosine_paraphrase": round(_cos(a, b), 4), "cosine_unrelated": round(_cos(a, c), 4)}
    return result(PASS, f"{target}: {len(a)}-d vectors; informational only (one pair): paraphrase "
                        f"{info['cosine_paraphrase']}, unrelated {info['cosine_unrelated']}",
                  target=target, **info)


def check_llm(cfg_path: Path = ROOT / "config.yaml", make_client: Optional[Callable] = None) -> Dict:
    import comment_extractor as ce            # also loads .env next to the extractor
    from config_utils import strict_true
    cfg = ce.Config.from_yaml(cfg_path)
    target = f"{cfg.llm_base_url} model {cfg.llm_model}"
    if not os.getenv(cfg.llm_api_key_env):
        return result(NOT_CONFIGURED, f"{cfg.llm_api_key_env} is not set; no call made", target=target)
    try:
        llm = (make_client or ce.LLMClient)(cfg)
        t0 = time.time()
        reply = llm.chat_json("You are a JSON API. Reply with JSON only.",
                              'Return exactly this JSON object with the sum filled in: {"ok": true, "sum": <2+3>}')
        secs = round(time.time() - t0, 1)
    except Exception as e:
        return result(FAIL, f"call to {target} failed: {_err(e)}", target=target)
    if not isinstance(reply, dict):
        return result(FAIL, f"{target}: reply was not a JSON object ({type(reply).__name__})", target=target)
    if not strict_true(reply.get("ok")) or reply.get("sum") not in (5, "5"):
        return result(FAIL, f"{target}: JSON parsed but content wrong: {json.dumps(reply)[:120]}", target=target)
    return result(PASS, f"{target}: valid JSON with the expected content in {secs}s", target=target)


CHECK_ORDER = ["postgres", "postgres_temp_db", "qdrant", "embedding", "llm"]


def exit_code(results: Dict[str, Dict]) -> int:
    statuses = [r["status"] for r in results.values()]
    if FAIL in statuses:
        return 1
    return 0 if statuses and all(s == PASS for s in statuses) else 3


def main(argv=None, checks: Optional[Dict[str, Callable[[], Dict]]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pg-temp-db", action="store_true", help="also run the temporary-database round trip")
    ap.add_argument("--only", default="", help="comma-separated subset of: " + ", ".join(CHECK_ORDER))
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--json", default=None, help="also write the results to this JSON file")
    args = ap.parse_args(argv)

    available = checks or {
        "postgres": check_postgres,
        "postgres_temp_db": lambda: check_postgres_temp_db(args.pg_temp_db),
        "qdrant": check_qdrant,
        "embedding": check_embedding,
        "llm": lambda: check_llm(Path(args.config)),
    }
    wanted = [c.strip() for c in args.only.split(",") if c.strip()] or [c for c in CHECK_ORDER if c in available]
    unknown = [c for c in wanted if c not in available]
    if unknown:
        ap.error(f"unknown check(s): {', '.join(unknown)}")
    results = {}
    for name in wanted:
        try:
            results[name] = available[name]()
        except Exception as e:                       # a bug in a check is a failure, not a pass
            results[name] = result(FAIL, f"check crashed: {_err(e)}")
        print(f"{name:18s} {results[name]['status']:15s} {results[name]['detail']}")
    code = exit_code(results)
    summary = {PASS: "all checks passed", FAIL: "at least one check FAILED"}.get(
        {0: PASS, 1: FAIL}.get(code, ""), "nothing failed, but not everything was verified (see SKIPPED / NOT_CONFIGURED)")
    print(f"\nResult: {summary}")
    if args.json:
        Path(args.json).write_text(json.dumps({"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                                               "results": results, "exit_code": code}, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())

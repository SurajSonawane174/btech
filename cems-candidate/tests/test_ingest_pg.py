"""
Ingest against a REAL PostgreSQL: database/schema.sql is applied to a throw-away database,
database/db.py runs unmodified, only Qdrant/Ollama are stubbed.

Skipped unless CEMS_TEST_DATABASE_URL points at a server where the user may CREATE DATABASE,
e.g. the docker-compose Postgres:
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


def test_counts_idempotency_conflicts_and_revisions_on_real_postgres(pg):
    from test_ingest import rows, SHA_A, SHA_B, SHA_C
    ingest, db, conn = pg

    t1 = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A, rev="RA", texts=["NA", "Verify weld"])), "rev A")
    assert (t1["comments"], t1["embedded"]) == (2, 2)
    assert q(conn, "SELECT count(*) FROM comments")[0][0] == 2
    assert q(conn, "SELECT actual_extracted_comment FROM comments ORDER BY sr_no")[0][0] == "NA"
    assert q(conn, "SELECT total_comments FROM revisions")[0][0] == 2          # real count, not len(records)

    t2 = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A, rev="RA", texts=["NA", "Verify weld"])), "rev A again")
    assert (t2["comments"], t2["already_present"]) == (0, 2)                    # idempotent, SELECT-counted

    t3 = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_B, rev="RA")), "other file, same revision")
    assert t3["comments"] == 0 and len(t3["conflicts"]) == 1
    assert q(conn, "SELECT count(*) FROM comments")[0][0] == 2                  # not merged

    t4 = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_C, rev="RB")), "rev B")
    assert t4["comments"] == 2
    assert sorted(r[0] for r in q(conn, "SELECT praj_revision_number FROM revisions")) == ["RA", "RB"]
    assert q(conn, "SELECT count(*) FROM comments WHERE embedded")[0][0] == 4

"""cems_cli.py: one JSON object on stdout, exit codes, the --confirm guard, stdin text for resolve."""
import io
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cems_cli  # noqa: E402


@pytest.fixture
def stubs(monkeypatch):
    from database import db
    monkeypatch.setattr(db, "init_pool", lambda **kw: None)
    calls = {}
    cs = types.ModuleType("vectordb.comment_sync")

    def resolve_comment(pk, text):
        calls["resolve"] = (pk, text)
        if pk == 404:
            raise LookupError("comment 404 not found")
        return {"comment": {"id": pk, "status": "closed", "resolution_text": text}, "warning": None}
    cs.resolve_comment = resolve_comment
    cs.reopen_comment = lambda pk: {"comment": {"id": pk, "status": "open", "resolved_at": None}, "warning": None}
    cs.sync_embeddings = lambda ids=None: calls.setdefault("sync", ids) or {"embedded": 0, "failed": 0}
    monkeypatch.setitem(sys.modules, "vectordb.comment_sync", cs)
    import vectordb
    monkeypatch.setattr(vectordb, "comment_sync", cs, raising=False)
    return calls


def out(capsys):
    text = capsys.readouterr().out
    assert len(text.strip().splitlines()) == 1          # exactly one JSON line on stdout
    return json.loads(text)


def test_resolve_reads_approved_text_from_stdin(stubs, capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("Weld resized to 8 mm.\n"))
    assert cems_cli.main(["resolve", "--comment-id", "12", "--text-stdin"]) == 0
    r = out(capsys)
    assert r["ok"] is True and r["result"]["comment"]["status"] == "closed"
    assert stubs["resolve"] == (12, "Weld resized to 8 mm.\n")


def test_not_found_is_a_handled_error(stubs, capsys):
    assert cems_cli.main(["resolve", "--comment-id", "404", "--text", "x"]) == 1
    r = out(capsys)
    assert r == {"ok": False, "command": "resolve", "error": "comment 404 not found"}


def test_reopen_and_embed_sync_ids(stubs, capsys):
    assert cems_cli.main(["reopen", "--comment-id", "5"]) == 0
    assert out(capsys)["result"]["comment"]["status"] == "open"
    cems_cli.main(["embed-sync", "--ids", "3,4"])
    out(capsys)
    assert stubs["sync"] == [3, 4]


def test_rebuild_requires_confirm(stubs, capsys):
    assert cems_cli.main(["rebuild-vectors"]) == 2
    assert "add --confirm" in out(capsys)["error"]


def test_ingest_requires_the_upload_form_fields():
    with pytest.raises(SystemExit):
        cems_cli.main(["ingest", "--input", "x.csv", "--project", "P"])     # --supplier / --po missing


def test_json_handles_dates_and_decimals():
    from datetime import datetime
    from decimal import Decimal
    assert json.loads(json.dumps({"t": datetime(2026, 3, 12, 10, 15), "c": Decimal("75")},
                                 default=cems_cli._json_default)) == {"t": "2026-03-12T10:15:00", "c": 75.0}

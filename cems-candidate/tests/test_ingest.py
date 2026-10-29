"""
Loader (ingest.py) tests for the FINAL schema.

* test_ingest.py (this file): pure mapping/date logic, plus ingest scenarios against an in-memory
  fake of database.db with the same uniqueness rules as schema.sql. No services needed.
* test_ingest_pg.py: the same scenarios on a REAL PostgreSQL (schema.sql applied to a throw-away
  database). Skipped unless CEMS_TEST_DATABASE_URL is set.
"""
import sys
import types
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHA_A = "a1" * 32
SHA_B = "b2" * 32
SHA_C = "c3" * 32
FORM = dict(praj_project_number="P-1001", supplier_name="ACME Fabricators", supplier_po_number="PO-1")


def import_ingest_with_stubbed_vectors():
    """Import ingest.py without qdrant-client / ollama; embedding sync is recorded, not run."""
    calls = {"syncs": 0}
    cs = types.ModuleType("vectordb.comment_sync")

    def sync_embeddings(ids=None, batch_size=200):
        calls["syncs"] += 1
        return {"embedded": 0, "failed": 0, "failed_ids": []}
    cs.sync_embeddings = sync_embeddings
    sys.modules["vectordb.comment_sync"] = cs
    import vectordb
    vectordb.comment_sync = cs
    sys.modules.pop("ingest", None)
    import ingest
    return ingest, calls


def rows(sha, drawing="DWG101", rev="RA", n=2, texts=None, rev_src="filename", dwg_src="filename",
         source_path=None, project="PRJ", date="12/03/2026", time="10:15:00"):
    texts = texts or [f"comment {i}" for i in range(n)]
    out = []
    for i, t in enumerate(texts, start=1):
        d_seg = "".join(ch for ch in drawing.upper() if ch.isalnum()) or "UNKNOWN"
        r_seg = "".join(ch for ch in rev.upper() if ch.isalnum()) or "NA"
        out.append({
            "source_file": Path(source_path or f"{drawing}_{rev}.pdf").name,
            "source_path": source_path or f"input/{drawing}_{rev}.pdf",
            "sr_no": str(i), "praj_document_number": drawing, "praj_revision_number": rev,
            "customer_document_number": "NA", "customer_revision": "NA", "page_sheet": "1",
            "comment_id": f"{project}-{d_seg}-{r_seg}-001-0{i:02d}-{i:03d}-{sha[:12].upper()}",
            "actual_extracted_comment": t, "snapshot_file": f"output/x/{i}.png",
            "name_of_person_commented": "Reviewer", "email_of_person_commented": "r@x.com",
            "date_of_comment": date, "time_of_comment": time, "comment_color": "Yellow",
            "is_client_comment": "Y", "comment_category": "technical", "is_handwritten": "N",
            "extraction_confidence_percent": "100", "annotation_type": "Text",
            "classification_method": "rule", "comment_source": "native", "visual_feature": "",
            "position_key": f"P001-R0{i:02d}-C010", "drawing_number_source": dwg_src,
            "revision_source": rev_src, "source_file_sha256": sha, "metadata_notes": "",
        })
    return out


class FakeDB:
    """In-memory stand-in for database.db: unique_doc_revision on documents, UNIQUE comment_id."""
    MISSING_REVISION = "NA"

    def __init__(self):
        self.documents, self.comments, self.n = {}, {}, 0

    def find_document(self, project, drawing, rev, supplier, po):
        return self.documents.get((project, drawing, rev or "NA", supplier, po), {}).get("id")

    def upsert_document(self, project, drawing, rev, supplier, po, cust_doc=None, cust_rev=None):
        key = (project, drawing, rev or "NA", supplier, po)
        if key not in self.documents:
            self.n += 1
            self.documents[key] = {"id": self.n, "customer_document_number": None if cust_doc in (None, "NA") else cust_doc}
        return self.documents[key]["id"]

    def comment_id_owners(self, ids):
        return {c: self.comments[c]["document_id"] for c in ids if c in self.comments}

    def get_comment_ids_for_document(self, document_id):
        return [k for k, v in self.comments.items() if v["document_id"] == document_id]

    def insert_comments(self, document_id, rows):
        before = len(self.comments)
        for r in rows:
            self.comments.setdefault(r["comment_id"], dict(r, document_id=document_id))   # ON CONFLICT DO NOTHING
        return len(self.comments) - before


@pytest.fixture
def env(monkeypatch):
    ingest, calls = import_ingest_with_stubbed_vectors()
    fake = FakeDB()
    for name in ("find_document", "upsert_document", "comment_id_owners", "get_comment_ids_for_document",
                 "insert_comments"):
        monkeypatch.setattr(ingest.db, name, getattr(fake, name))
    return ingest, fake, calls


def run(ingest, data, **kw):
    form = dict(FORM)
    form.update({k: kw.pop(k) for k in list(kw) if k in form})
    return ingest.ingest_dataframe(pd.DataFrame(data), "t", **form, **kw)


# ---------------------------------------------------------------- pure mapping

def test_read_keeps_literal_na_text(tmp_path):
    ingest, _ = import_ingest_with_stubbed_vectors()
    df = pd.DataFrame(rows(SHA_A, texts=["NA", "None", "null"]))
    p = tmp_path / "m.csv"
    df.to_csv(p, index=False)
    back = ingest.read_extractor_csv(p)
    assert list(back.actual_extracted_comment) == ["NA", "None", "null"]
    assert back.loc[0, "customer_document_number"] == "NA"
    assert pd.isna(back.loc[0, "visual_feature"])


@pytest.mark.parametrize("date,time,expected", [
    ("12/03/2026", "10:15:00", datetime(2026, 3, 12, 10, 15, 0)),      # native: DD/MM/YYYY
    ("2026-03-02", "10:15", datetime(2026, 3, 2, 10, 15, 0)),          # vision box: ISO, HH:MM
    ("25/03/2026", "09:05:30", datetime(2026, 3, 25, 9, 5, 30)),       # day > 12 is still day-first
    ("12-09-2026", "14:25", None),                                     # ambiguous OCR date: not guessed
    ("12/09/26", "14:25", None), ("2026/09/12", "14:25", None),
    ("31/02/2026", "10:00", None),                                     # impossible date
    ("12/03/2026", "NA", None), ("NA", "10:15:00", None), (None, None, None), ("", "", None),
    ("12/03/2026", "25:00", None),
])
def test_comment_datetime_parsing(date, time, expected):
    ingest, _ = import_ingest_with_stubbed_vectors()
    assert ingest.parse_comment_datetime(date, time) == expected


def test_mapping_is_an_explicit_allowlist():
    ingest, _ = import_ingest_with_stubbed_vectors()
    from database import db
    m = ingest.map_comment_row(rows(SHA_A)[0])
    assert set(m) == set(db.COMMENT_INSERT_COLUMNS)
    assert m["is_client_comment"] is True and m["is_handwritten"] is False
    assert m["extraction_confidence_percent"] == Decimal("100") and m["page_sheet"] == "1"
    assert m["comment_datetime"] == datetime(2026, 3, 12, 10, 15)
    empty = ingest.map_comment_row({"comment_id": "X", "actual_extracted_comment": "t",
                                    "extraction_confidence_percent": "", "page_sheet": "2"})
    assert empty["extraction_confidence_percent"] is None and empty["is_client_comment"] is False
    dropped = ingest.dropped_columns(pd.DataFrame(rows(SHA_A)))
    assert {"sr_no", "email_of_person_commented", "annotation_type", "classification_method",
            "comment_source", "visual_feature", "position_key", "metadata_notes"} <= set(dropped)
    assert "comment_id" not in dropped and "date_of_comment" not in dropped


# ---------------------------------------------------------------- scenarios

def test_two_revisions_land_in_two_document_rows(env):
    ingest, fake, calls = env
    t = run(ingest, rows(SHA_A, rev="RA") + rows(SHA_B, rev="RB"))
    assert t["comments"] == 4 and not t["skipped"] and not t["conflicts"]
    assert sorted(k[2] for k in fake.documents) == ["RA", "RB"] and calls["syncs"] == 1


def test_reingesting_same_file_is_idempotent(env):
    ingest, fake, _ = env
    first, second = run(ingest, rows(SHA_A)), run(ingest, rows(SHA_A))
    assert (first["comments"], second["comments"], second["already_present"]) == (2, 0, 2)
    assert len(fake.documents) == 1


def test_different_file_claiming_same_revision_is_a_conflict_not_a_merge(env):
    ingest, fake, _ = env
    run(ingest, rows(SHA_A))
    t = run(ingest, rows(SHA_B))
    assert t["comments"] == 0 and len(t["conflicts"]) == 1 and "another source file" in t["conflicts"][0]["reason"]


def test_same_pdf_under_another_supplier_or_po_is_a_conflict(env):
    ingest, fake, _ = env
    run(ingest, rows(SHA_A))
    t = run(ingest, rows(SHA_A), supplier_name="Other Supplier")
    assert t["comments"] == 0 and len(t["conflicts"]) == 1
    assert "globally unique" in t["conflicts"][0]["reason"]
    assert len(fake.documents) == 1                      # no empty document row was created
    t = run(ingest, rows(SHA_A), supplier_po_number="PO-2")
    assert len(t["conflicts"]) == 1 and len(fake.documents) == 1


def test_missing_revision_is_stored_as_na_and_is_idempotent(env):
    ingest, fake, _ = env
    t1 = run(ingest, rows(SHA_A, rev="NA", rev_src="unresolved"))
    t2 = run(ingest, rows(SHA_A, rev="NA", rev_src="unresolved"))
    assert (t1["comments"], t2["comments"]) == (2, 0) and not t1["skipped"]
    assert [k[2] for k in fake.documents] == ["NA"]


def test_unresolved_drawing_is_skipped_unless_allowed(env):
    ingest, fake, _ = env
    t = run(ingest, rows(SHA_A, drawing="UNKNOWN", dwg_src="unresolved"))
    assert t["comments"] == 0 and "unresolved drawing number" in t["skipped"][0]["reason"] and not fake.documents
    t = run(ingest, rows(SHA_A, drawing="UNKNOWN", dwg_src="unresolved"), allow_unresolved=True)
    assert t["comments"] == 2
    assert [k[1] for k in fake.documents] == [f"UNRESOLVED-{SHA_A[:12].upper()}"]


def test_form_fields_are_required_and_never_defaulted(env):
    ingest, fake, _ = env
    for field in ("praj_project_number", "supplier_name", "supplier_po_number"):
        with pytest.raises(ValueError, match="required"):
            run(ingest, rows(SHA_A), **{field: ""})
    assert not fake.documents


def test_rows_without_text_and_unparseable_dates_are_counted(env):
    ingest, fake, _ = env
    data = rows(SHA_A, texts=["keep", "", "ambiguous"])
    data[2]["date_of_comment"], data[2]["time_of_comment"] = "12-09-2026", "14:25"
    t = run(ingest, data)
    assert t["comments"] == 2 and t["rows_without_text"] == 1 and t["datetime_not_stored"] == 1
    stored = {c["actual_extracted_comment"]: c for c in fake.comments.values()}
    assert stored["ambiguous"]["comment_datetime"] is None
    assert stored["keep"]["comment_datetime"] == datetime(2026, 3, 12, 10, 15)


def test_rows_of_one_file_with_conflicting_revisions_are_rejected(env):
    ingest, fake, _ = env
    data = rows(SHA_A)
    data[1]["praj_revision_number"] = "RB"
    t = run(ingest, data)
    assert t["comments"] == 0 and "disagree" in t["skipped"][0]["reason"]


def test_no_embed_skips_the_sync(env):
    ingest, _, calls = env
    run(ingest, rows(SHA_A), embed=False)
    assert calls["syncs"] == 0

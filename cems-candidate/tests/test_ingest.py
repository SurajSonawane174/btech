"""
Ingest integrity tests (Chunk A4).

* test_ingest.py (this file): ingest.py logic against an in-memory fake of database.db,
  with Qdrant/Ollama stubbed. Needs no services; runs everywhere.
* test_ingest_pg.py: the same scenarios against a REAL PostgreSQL (schema.sql applied to a
  throw-away database). Skipped unless CEMS_TEST_DATABASE_URL is set.
"""
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHA_A = "a1" * 32
SHA_B = "b2" * 32
SHA_C = "c3" * 32


def import_ingest_with_stubbed_vectors():
    """Import ingest.py without qdrant-client / ollama installed or running."""
    calls = {"upserts": [], "embed_fail": False, "upsert_fail": False}
    qd = types.ModuleType("vectordb.qdrant_client")
    qd.upsert_comment_embeddings_bulk = lambda items: (
        (_ for _ in ()).throw(RuntimeError("qdrant down")) if calls["upsert_fail"] else calls["upserts"].extend(items))
    qd.ensure_collections = lambda: None
    em = types.ModuleType("vectordb.embedder")

    def embed_text(text):
        if calls["embed_fail"]:
            raise RuntimeError("ollama down")
        return [0.1] * 768
    em.embed_text = embed_text
    em.check_ready = lambda: True
    sys.modules["vectordb.qdrant_client"] = qd
    sys.modules["vectordb.embedder"] = em
    import vectordb
    vectordb.qdrant_client, vectordb.embedder = qd, em
    sys.modules.pop("ingest", None)
    import ingest
    return ingest, calls


def rows(sha, drawing="DWG101", rev="RA", n=2, texts=None, rev_src="filename", dwg_src="filename",
         source_path=None, project="PRJ"):
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
            "name_of_person_commented": "Reviewer", "email_of_person_commented": "",
            "date_of_comment": "NA", "time_of_comment": "NA", "comment_color": "Yellow",
            "is_client_comment": "Y", "comment_category": "technical", "is_handwritten": "N",
            "extraction_confidence_percent": "100", "annotation_type": "Text",
            "classification_method": "rule", "comment_source": "native", "visual_feature": "",
            "position_key": f"P001-R0{i:02d}-C010", "drawing_number_source": dwg_src,
            "revision_source": rev_src, "source_file_sha256": sha, "metadata_notes": "",
        })
    return out


class FakeDB:
    """In-memory stand-in for database.db with the same uniqueness rules as schema.sql."""

    def __init__(self):
        self.projects, self.documents, self.revisions, self.comments = {}, {}, {}, {}
        self.n = 0

    def _id(self):
        self.n += 1
        return f"id{self.n}"

    def get_or_create_project(self, project_code, **_):
        return self.projects.setdefault(project_code, self._id())

    def get_or_create_document(self, project_id, drawing_number, **_):
        return self.documents.setdefault((project_id, drawing_number), self._id())

    def find_revision(self, document_id, praj_revision_number):
        r = self.revisions.get((document_id, praj_revision_number))
        return r["id"] if r else None

    def create_revision(self, document_id, praj_revision_number, source_pdf_path=None, **_):
        key = (document_id, praj_revision_number)
        if key not in self.revisions:
            self.revisions[key] = {"id": self._id(), "source_pdf_path": source_pdf_path}
        else:
            self.revisions[key]["source_pdf_path"] = source_pdf_path
        return self.revisions[key]["id"]

    def insert_comments_bulk(self, revision_id, records):
        before = sum(1 for (r, _) in self.comments if r == revision_id)
        for rec in records:
            key = (revision_id, rec["comment_id"])
            if key not in self.comments:                   # ON CONFLICT DO NOTHING
                self.comments[key] = {"id": self._id(), "comment_uid": rec["comment_id"],
                                      "actual_extracted_comment": rec["actual_extracted_comment"],
                                      "comment_category": rec["comment_category"], "embedded": False}
        return sum(1 for (r, _) in self.comments if r == revision_id) - before

    def get_comments_by_revision(self, revision_id):
        return [dict(c) for (r, _), c in self.comments.items() if r == revision_id]

    def mark_comments_embedded(self, ids):
        for c in self.comments.values():
            if c["id"] in ids:
                c["embedded"] = True


@pytest.fixture
def env(monkeypatch):
    ingest, calls = import_ingest_with_stubbed_vectors()
    fake = FakeDB()
    for name in ("get_or_create_project", "get_or_create_document", "find_revision", "create_revision",
                 "insert_comments_bulk", "get_comments_by_revision", "mark_comments_embedded"):
        monkeypatch.setattr(ingest.db, name, getattr(fake, name))
    return ingest, fake, calls


def test_read_keeps_literal_na_text(tmp_path):
    ingest, _ = import_ingest_with_stubbed_vectors()
    df = pd.DataFrame(rows(SHA_A, texts=["NA", "None", "null"]))
    df.loc[0, "visual_feature"] = ""
    p = tmp_path / "m.csv"
    df.to_csv(p, index=False)
    back = ingest.read_extractor_csv(p)
    assert list(back.actual_extracted_comment) == ["NA", "None", "null"]     # text kept as text
    assert back.loc[0, "customer_document_number"] == "NA"
    assert pd.isna(back.loc[0, "visual_feature"])                            # only empty -> missing


def test_two_revisions_land_in_two_revision_rows(env):
    ingest, fake, _ = env
    df = pd.DataFrame(rows(SHA_A, rev="RA") + rows(SHA_B, rev="RB"))
    t = ingest.ingest_dataframe(df, "test")
    assert t["comments"] == 4 and not t["skipped"] and not t["conflicts"]
    assert len(fake.revisions) == 2 and len(fake.documents) == 1


def test_reingesting_same_file_is_idempotent(env):
    ingest, fake, _ = env
    df = pd.DataFrame(rows(SHA_A))
    first = ingest.ingest_dataframe(df, "run1")
    second = ingest.ingest_dataframe(df, "run2")
    assert (first["comments"], second["comments"], second["already_present"]) == (2, 0, 2)
    assert not second["conflicts"] and len(fake.comments) == 2


def test_different_file_claiming_same_revision_is_a_conflict_not_a_merge(env):
    ingest, fake, _ = env
    ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A)), "first")
    t = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_B, texts=["comment 0", "comment 1"])), "second")
    assert t["comments"] == 0 and len(t["conflicts"]) == 1
    assert len(fake.comments) == 2                                           # nothing merged


def test_identical_text_in_unrelated_files_is_not_merged(env):
    ingest, fake, _ = env
    same = ["Check nozzle orientation", "Verify weld size"]
    df = pd.DataFrame(rows(SHA_A, drawing="DWG101", texts=same) + rows(SHA_B, drawing="DWG202", texts=same))
    t = ingest.ingest_dataframe(df, "test")
    assert t["comments"] == 4 and len(fake.documents) == 2


def test_unresolved_metadata_is_skipped_by_default(env):
    ingest, fake, _ = env
    df = pd.DataFrame(rows(SHA_A, drawing="UNKNOWN", rev="NA", rev_src="unresolved", dwg_src="unresolved")
                      + rows(SHA_B, drawing="DWG101", rev="NA", rev_src="unresolved"))
    t = ingest.ingest_dataframe(df, "test")
    assert t["comments"] == 0 and len(t["skipped"]) == 2 and not fake.revisions
    reasons = sorted(x["reason"] for x in t["skipped"])
    assert reasons[0].startswith("unresolved drawing number and revision")
    assert reasons[1].startswith("unresolved revision")


def test_allow_unresolved_isolates_each_file(env):
    """Two unresolved files must not end up in one shared 'UNKNOWN/NA' revision."""
    ingest, fake, _ = env
    df = pd.DataFrame(rows(SHA_A, drawing="UNKNOWN", rev="NA", rev_src="unresolved", dwg_src="unresolved")
                      + rows(SHA_B, drawing="UNKNOWN", rev="NA", rev_src="unresolved", dwg_src="unresolved")
                      + rows(SHA_C, drawing="DWG101", rev="NA", rev_src="unresolved"))
    t = ingest.ingest_dataframe(df, "test", allow_unresolved=True)
    assert t["comments"] == 6 and not t["conflicts"]
    drawings = {d for (_, d) in fake.documents}
    assert drawings == {f"UNRESOLVED-{SHA_A[:12].upper()}", f"UNRESOLVED-{SHA_B[:12].upper()}", "DWG101"}
    assert sorted(rev for (_, rev) in fake.revisions) == sorted(
        [f"NA-{SHA_A[:8].upper()}", f"NA-{SHA_B[:8].upper()}", f"NA-{SHA_C[:8].upper()}"])


def test_revision_zero_and_text_na_are_not_treated_as_missing(env):
    ingest, fake, _ = env
    t = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A, rev="0", texts=["NA", "ok"])), "test")
    assert t["comments"] == 2 and not t["skipped"]
    assert any(rev == "0" for (_, rev) in fake.revisions)
    assert {c["actual_extracted_comment"] for c in fake.comments.values()} == {"NA", "ok"}


def test_embedding_failure_keeps_rows_and_retries_later(env):
    ingest, fake, calls = env
    calls["upsert_fail"] = True
    t1 = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A)), "run1")
    assert (t1["comments"], t1["embedded"], t1["embedding_failed"]) == (2, 0, 2)
    assert not any(c["embedded"] for c in fake.comments.values())
    calls["upsert_fail"] = False
    t2 = ingest.ingest_dataframe(pd.DataFrame(rows(SHA_A)), "run2")
    assert (t2["comments"], t2["embedded"]) == (0, 2)                         # retried, not re-inserted


def test_legacy_csv_without_source_hash_still_ingests(env):
    ingest, fake, _ = env
    legacy = pd.DataFrame(rows(SHA_A)).drop(columns=["source_file_sha256", "drawing_number_source",
                                                     "revision_source", "position_key", "metadata_notes"])
    t = ingest.ingest_dataframe(legacy, "legacy")
    assert t["comments"] == 2


def test_rows_of_one_file_with_conflicting_revisions_are_rejected(env):
    ingest, fake, _ = env
    bad = rows(SHA_A)
    bad[1]["praj_revision_number"] = "RB"
    t = ingest.ingest_dataframe(pd.DataFrame(bad), "bad")
    assert t["comments"] == 0 and "disagree" in t["skipped"][0]["reason"]

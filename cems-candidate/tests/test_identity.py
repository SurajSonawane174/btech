"""
Comment identity regression tests (known issue 6.1 in docs/HANDOFF.md).

They guard the identity fix and must keep passing:
  * different source files with identical layouts and look-alike filenames
    (CEMS_Engineering_Annotation_Set_<N>.pdf) do not share comment_ids. Before the fix
    all five parsed to drawing="Annotation", revision="Set" and produced only 3 distinct
    ids for 15 comments, which downstream inserts then dropped;
  * Rev A and Rev B of the same drawing do not share comment_ids;
  * re-running the same file gives the same ids (idempotent reprocessing);
  * metadata is validated before use, with its provenance recorded;
  * source_file_sha256, not comment_id, identifies duplicate PDFs;
  * position_key is a non-unique matching hint.
The id hash suffix (12 hex of source_file_sha256) distinguishes source files
probabilistically, not with certainty.
"""
import dataclasses
import sys
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import comment_extractor as ce  # noqa: E402

# Same three annotations, same positions, in every file: the worst case for collisions.
LAYOUT = [
    ((100, 100), "Verify fillet weld size per AWS D1.1"),
    ((300, 250), "Relocate valve V-12 for maintenance clearance"),
    ((500, 400), "Font in title block too small"),
]


def make_pdf(path: Path, pages: int = 1):
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page(width=842, height=595)
        for pos, text in LAYOUT:
            a = page.add_text_annot(pos, text)
            a.set_info(title="Reviewer")
            a.update()
    doc.save(path)


@pytest.fixture
def cfg():
    base = ce.Config.from_yaml(ROOT / "config.yaml")
    # fully local: no LLM, no vision, no OCR -> deterministic and offline
    return dataclasses.replace(base, vision_enabled=False, ocr_enabled=False,
                               enrichment_enabled=False, metadata_llm_enabled=False,
                               classification_llm_enabled=False)


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _ids(pdf: Path, cfg) -> list:
    n, df = ce.process_pdf(pdf, cfg, None, False)
    assert n == len(LAYOUT)
    return list(df.comment_id)


def test_different_files_never_share_comment_ids(cfg, work):
    """Five distinct files with identical layouts -> 15 distinct ids (before the fix: 3)."""
    all_ids = []
    for i in range(1, 6):
        pdf = work / f"CEMS_Engineering_Annotation_Set_{i}.pdf"
        make_pdf(pdf)
        all_ids += _ids(pdf, cfg)
    dupes = sorted({x for x in all_ids if all_ids.count(x) > 1})
    assert len(set(all_ids)) == len(all_ids), (
        f"{len(all_ids)} comments but only {len(set(all_ids))} distinct ids; "
        f"colliding ids: {dupes[:5]}")


def test_revisions_of_same_drawing_get_distinct_ids(cfg, work):
    """Rev A and Rev B of one drawing, same comment positions -> ids must differ."""
    ra, rb = work / "PRJ_PID_DWG101_RA.pdf", work / "PRJ_PID_DWG101_RB.pdf"
    make_pdf(ra)
    make_pdf(rb)
    ids_a, ids_b = _ids(ra, cfg), _ids(rb, cfg)
    assert not set(ids_a) & set(ids_b), f"Rev A and Rev B share ids: {sorted(set(ids_a) & set(ids_b))}"


def test_reprocessing_same_file_gives_same_ids(cfg, work):
    """Idempotency guard: the fix must not make ids random or run-dependent."""
    pdf = work / "PRJ_PID_DWG101_RA.pdf"
    make_pdf(pdf)
    first = _ids(pdf, cfg)
    second = _ids(pdf, cfg)
    assert first == second


# ---------------------------------------------------------------- id format and copies

def test_renamed_byte_identical_copy_shares_source_hash_not_full_id(cfg, work):
    """source_file_sha256 identifies the PDF bytes. A byte-identical copy under another
    name has the same source hash and the same id hash suffix, but its full comment_id can
    differ because PROJECT/DRAWING/REV are derived from the filename. So different full
    ids do not prove different documents: duplicates must be detected on
    source_file_sha256, not on comment_id."""
    import shutil
    a = work / "PRJ_PID_DWG101_RA.pdf"
    make_pdf(a)
    b = work / "copy_of_drawing.pdf"
    shutil.copy(a, b)
    _, df_a = ce.process_pdf(a, cfg, None, False)
    _, df_b = ce.process_pdf(b, cfg, None, False)

    # same bytes -> same source hash, and the id suffix is derived from it
    assert set(df_a.source_file_sha256) == set(df_b.source_file_sha256)
    assert df_a.source_file_sha256.nunique() == 1
    suffix = df_a.source_file_sha256.iloc[0][:ce.UID_HASH_HEX].upper()
    assert [i.split("-")[-1] for i in df_a.comment_id] == [suffix] * len(LAYOUT)
    assert [i.split("-")[-1] for i in df_b.comment_id] == [suffix] * len(LAYOUT)

    # ... but the full ids differ, because the filename-derived metadata differs
    assert (df_a.praj_document_number.iloc[0], df_b.praj_document_number.iloc[0]) == ("DWG101", "UNKNOWN")
    assert not set(df_a.comment_id) & set(df_b.comment_id)


def test_different_pdfs_differ_in_source_hash(cfg, work):
    """Counterpart: two separately generated files with the same layout have different bytes,
    hence different source hashes (this is what keeps their ids apart)."""
    a, b = work / "PRJ_PID_DWG101_RA.pdf", work / "PRJ_PID_DWG102_RA.pdf"
    make_pdf(a)
    make_pdf(b)
    _, df_a = ce.process_pdf(a, cfg, None, False)
    _, df_b = ce.process_pdf(b, cfg, None, False)
    assert df_a.source_file_sha256.iloc[0] != df_b.source_file_sha256.iloc[0]


def test_id_structure_and_length_limit(cfg, work):
    pdf = work / "PRJ_PID_DWG101_RA.pdf"
    make_pdf(pdf)
    n, df = ce.process_pdf(pdf, cfg, None, False)
    uid = df.comment_id.iloc[0]
    parts = uid.split("-")
    assert parts[:3] == ["PRJ", "DWG101", "RA"]          # project, drawing, revision
    assert ce.UID_HASH_HEX == 12
    assert len(parts) == 7 and len(parts[-1]) == 12       # ... page-row-seq-HASH12
    assert parts[-1] == df.source_file_sha256.iloc[0][:12].upper()
    assert all(len(i) <= ce.UID_MAX_LEN for i in df.comment_id)


# ---------------------------------------------------------------- C2: length budget and suffix

SHA = "0123456789abcdef" * 4          # a 64-hex digest for direct make_uid calls


def _parse_uid_from_ingest():
    """ingest.py no longer parses comment_id (the project comes from --project); the ID format is
    still PROJECT-DRAWING-REV-page-row-seq-HASH12, so the first two segments are checked here."""
    def parse_uid(uid):
        parts = str(uid).split("-")
        return (parts[0], parts[1]) if len(parts) >= 4 else (parts[0] if parts else "UNKNOWN", "UNKNOWN")
    return parse_uid


def test_normal_metadata_is_not_shortened(cfg):
    """Max-cap metadata (20/40/8) with 3-digit numbers fits as-is: 95 characters."""
    meta = {"project": "P" * 20, "drawing_number": "D" * 39 + "1", "praj_revision": "R" * 8}
    uid = ce.make_uid(meta, 999, 1.0, 2.0, 999, cfg, SHA)
    assert uid == f"{'P' * 20}-{'D' * 39}1-{'R' * 8}-999-040-999-0123456789AB"
    assert len(uid) == 95


def test_long_metadata_shortens_prefix_not_suffix(cfg):
    meta = {"project": "P" * 60, "drawing_number": "D1" * 60, "praj_revision": "REV-B1234567"}
    for page, seq in [(999, 999), (12345, 99999), (999999, 999999)]:
        uid = ce.make_uid(meta, page, 1.0, 2.0, seq, cfg, SHA)
        parts = uid.split("-")
        assert len(uid) <= ce.UID_MAX_LEN, (page, seq, len(uid))
        assert len(parts) == 7 and all(parts)                     # structure kept, no empty segment
        assert parts[-1] == SHA[:12].upper()                      # full 12-hex suffix kept
        assert parts[3:6] == [f"{page:03d}", "040", f"{seq:03d}"]  # page/row/seq untouched
        assert uid == ce.make_uid(meta, page, 1.0, 2.0, seq, cfg, SHA)   # deterministic


def test_invalid_or_short_hash_is_rejected(cfg):
    meta = {"project": "PRJ", "drawing_number": "DWG101", "praj_revision": "RA"}
    for bad in ("abc", "z" * 64, "0123456789a"):
        with pytest.raises(ValueError):
            ce.make_uid(meta, 1, 1.0, 2.0, 1, cfg, bad)
    assert ce.make_uid(meta, 1, 1.0, 2.0, 1, cfg).count("-") == 5   # no hash -> legacy 6 segments


def test_ingest_parse_uid_still_reads_project_and_drawing(cfg, work):
    parse_uid = _parse_uid_from_ingest()
    pdf = work / "PRJ_PID_DWG-101_RA.pdf"
    make_pdf(pdf)
    _, df = ce.process_pdf(pdf, cfg, None, False)
    assert {parse_uid(u) for u in df.comment_id} == {("PRJ", "DWG101")}
    long_uid = ce.make_uid({"project": "P" * 60, "drawing_number": "D1" * 60, "praj_revision": "RA"},
                           12345, 1.0, 2.0, 99999, cfg, SHA)
    project, drawing = parse_uid(long_uid)
    # shortened, but still the PROJECT and DRAWING segments, in place
    assert project == "P" * len(project) and drawing.startswith("D1")
    assert long_uid.startswith(f"{project}-{drawing}-")


# ---------------------------------------------------------------- metadata and provenance

def _meta(work, name, cfg, docinfo=None):
    pdf = work / name
    make_pdf(pdf)
    if docinfo:
        doc = fitz.open(pdf)
        doc.set_metadata(docinfo)
        doc.saveIncr()
        doc.close()
    doc = fitz.open(pdf)
    try:
        return ce.extract_metadata(doc, name, None, cfg)
    finally:
        doc.close()


def test_implausible_filename_parts_are_not_trusted(cfg, work):
    m = _meta(work, "CEMS_Engineering_Annotation_Set_3.pdf", cfg)
    assert (m["drawing_number"], m["drawing_number_source"]) == ("UNKNOWN", "unresolved")
    assert (m["praj_revision"], m["revision_source"]) == ("NA", "unresolved")


def test_plausible_filename_is_used_with_provenance(cfg, work):
    m = _meta(work, "PRJ_PID_DWG-101_REV-B.pdf", cfg)
    assert (m["project"], m["drawing_number"], m["praj_revision"]) == ("PRJ", "DWG-101", "REV-B")
    assert m["drawing_number_source"] == m["revision_source"] == "filename"


def test_missing_revision_is_never_invented(cfg, work):
    """The old parser defaulted to 'R0'. Unknown must stay unknown."""
    m = _meta(work, "PRJ_PID_DWG101.pdf", cfg)
    assert m["drawing_number"] == "DWG101" and m["praj_revision"] == "NA"
    assert m["revision_source"] == "unresolved"


def test_pdf_metadata_fallback_only_when_labelled(cfg, work):
    m = _meta(work, "scan_0001.pdf", cfg, {"title": "Drawing No: DWG-4512, Rev: B"})
    assert (m["drawing_number"], m["drawing_number_source"]) == ("DWG-4512", "pdf_metadata")
    assert (m["praj_revision"], m["revision_source"]) == ("B", "pdf_metadata")
    unlabelled = _meta(work, "scan_0002.pdf", cfg, {"title": "Layout 4512 final B"})
    assert unlabelled["drawing_number_source"] == "unresolved"
    assert unlabelled["revision_source"] == "unresolved"


def test_filename_beats_pdf_metadata(cfg, work):
    m = _meta(work, "PRJ_PID_DWG101_RA.pdf", cfg, {"title": "Drawing No: OTHER-999, Rev: Z"})
    assert (m["drawing_number"], m["praj_revision"]) == ("DWG101", "RA")
    assert m["drawing_number_source"] == m["revision_source"] == "filename"


def test_provenance_columns_in_output(cfg, work):
    pdf = work / "CEMS_Engineering_Annotation_Set_1.pdf"
    make_pdf(pdf)
    n, df = ce.process_pdf(pdf, cfg, None, False)
    assert set(df.drawing_number_source) == {"unresolved"} and set(df.revision_source) == {"unresolved"}
    assert df.source_file_sha256.str.len().eq(64).all()


# ---------------------------------------------------------------- position_key

def test_position_key_matches_across_revisions_and_is_not_unique(cfg, work):
    ra, rb = work / "PRJ_PID_DWG101_RA.pdf", work / "PRJ_PID_DWG101_RB.pdf"
    make_pdf(ra)
    make_pdf(rb)
    _, dfa = ce.process_pdf(ra, cfg, None, False)
    _, dfb = ce.process_pdf(rb, cfg, None, False)
    assert list(dfa.position_key) == list(dfb.position_key)        # same spots -> same keys
    assert not set(dfa.comment_id) & set(dfb.comment_id)           # ... but different ids
    assert dfa.position_key.nunique() == len(LAYOUT)               # different spots differ
    r = fitz.Rect(100, 100, 120, 120)
    page = fitz.Rect(0, 0, 842, 595)
    assert ce.make_position_key(1, r, page, cfg) == ce.make_position_key(1, r + (1, 1, 1, 1), page, cfg)

def test_adding_comment_on_page_one_does_not_shift_page_two_ids(cfg, work):
    """Adding a comment on page 1 must not shift sequence numbers on page 2.
    The edit changes the file bytes (so the hash suffix changes); everything else in the
    page-2 ids must stay the same, and their seq segment must restart at 001 per page."""
    original = work / "PRJ_PID_DWG101_RA.pdf"
    make_pdf(original, pages=2)
    _, before = ce.process_pdf(original, cfg, None, False)

    doc = fitz.open(original)
    try:
        page = doc[0]
        annotation = page.add_text_annot((650, 150), "Additional review comment")
        annotation.set_info(title="Reviewer")
        annotation.update()
        doc.saveIncr()
    finally:
        doc.close()

    _, df = ce.process_pdf(original, cfg, None, False)

    page_two = df.loc[df["page_sheet"] == 2]
    assert len(page_two) == len(LAYOUT)
    assert list(page_two["sr_no"]) == list(range(5, 8))          # sr_no stays document-global
    seqs = [uid.split("-")[5] for uid in page_two["comment_id"]]
    assert seqs == ["001", "002", "003"]                          # per-page sequence (C3)
    strip_hash = lambda ids: ["-".join(u.split("-")[:-1]) for u in ids]
    assert strip_hash(page_two["comment_id"]) == strip_hash(
        before.loc[before["page_sheet"] == 2, "comment_id"])      # page-2 ids unchanged apart from hash

def test_rotated_page_position_keys_are_valid(cfg, work):
    """Position keys for native annotations on rotated pages remain valid."""
    pdf = work / "PRJ_PID_DWG101_RA.pdf"
    make_pdf(pdf, pages=2)

    doc = fitz.open(pdf)
    try:
        doc[1].set_rotation(90)
        doc.saveIncr()
    finally:
        doc.close()

    _, df = ce.process_pdf(pdf, cfg, None, False)

    assert len(df) == len(LAYOUT) * 2
    assert df["position_key"].notna().all()
    assert df["position_key"].str.fullmatch(
        r"P\d{3}-R\d{3}-C\d{3}"
    ).all()
    assert df.loc[df["page_sheet"] == 1, "position_key"].str.startswith(
        "P001-"
    ).all()
    assert df.loc[df["page_sheet"] == 2, "position_key"].str.startswith(
        "P002-"
    ).all()

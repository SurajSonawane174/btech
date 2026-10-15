"""
Chunk A regression tests: output collisions (C5), metadata validation (C6) and rotated-page
geometry. Offline: no LLM, no OCR model, no network. Geometry tests compare against the
annotation's RENDERED pixels, not just the key format.
"""
import dataclasses
import json
import shutil
import sys
from pathlib import Path

import fitz
import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import comment_extractor as ce  # noqa: E402

LAYOUT = [((100, 100), "Verify fillet weld size per AWS D1.1"),
          ((300, 250), "Relocate valve V-12 for maintenance clearance"),
          ((500, 400), "Font in title block too small")]


def make_pdf(path: Path, marker: str = ""):
    """Same three comments; `marker` changes page text so files differ in bytes and content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    if marker:
        page.insert_text((40, 560), marker, fontsize=8)
    for pos, text in LAYOUT:
        a = page.add_text_annot(pos, text)
        a.set_info(title="Reviewer")
        a.update()
    doc.save(path)


@pytest.fixture
def cfg():
    base = ce.Config.from_yaml(ROOT / "config.yaml")
    return dataclasses.replace(base, vision_enabled=False, ocr_enabled=False, enrichment_enabled=False,
                               metadata_llm_enabled=False, classification_llm_enabled=False)


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run_main(work: Path, input_dir: Path, monkeypatch):
    """Run the real CLI entry point fully offline (vision/LLM/OCR off -> no API key needed)."""
    y = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    y["vision"]["enabled"] = False
    y["llm"]["metadata_enabled"] = False
    y.setdefault("classification", {})["llm_enabled"] = False
    y.setdefault("ocr", {})["enabled"] = False
    y.setdefault("enrichment", {})["enabled"] = False
    cfg_path = work / "offline.yaml"
    cfg_path.write_text(yaml.safe_dump(y), encoding="utf-8")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["comment_extractor.py", "--input", str(input_dir), "--config", str(cfg_path)])
    ce.main()


# ============================================================ A1 / C5: same-name PDFs

def test_assign_output_names_unique_and_deterministic(work):
    a, b, c = work / "x/a/DWG.pdf", work / "x/b/DWG.pdf", work / "x/c/OTHER.pdf"
    make_pdf(a, "file a")
    make_pdf(b, "file b")
    make_pdf(c, "file c")
    names = ce.assign_output_names([a, b, c])
    assert names[c] == "OTHER"                                   # unique stem: unchanged
    assert names[a] == f"DWG__{ce.file_sha256(a)[:8]}"
    assert names[b] == f"DWG__{ce.file_sha256(b)[:8]}"
    assert len(set(names.values())) == 3
    assert names == ce.assign_output_names([c, b, a])            # input order does not matter


def test_byte_identical_same_name_files_still_get_separate_folders(work):
    a = work / "x/a/DWG.pdf"
    make_pdf(a)
    b = work / "x/b/DWG.pdf"
    b.parent.mkdir(parents=True)
    shutil.copy(a, b)
    names = ce.assign_output_names([a, b])
    base = f"DWG__{ce.file_sha256(a)[:8]}"
    assert sorted(names.values()) == [base, f"{base}__2"]


def test_same_name_pdfs_in_two_folders_keep_all_outputs(work, monkeypatch):
    """Before C5: 2 files x 3 comments -> 3 master rows; the second folder overwrote the first."""
    inp = work / "input"
    make_pdf(inp / "siteA" / "PRJ_PID_DWG101_RA.pdf", "site A")
    make_pdf(inp / "siteB" / "PRJ_PID_DWG101_RA.pdf", "site B")
    run_main(work, inp, monkeypatch)

    master = pd.read_csv(work / "output/master_comments.csv", dtype=str, keep_default_na=False)
    assert len(master) == 6
    assert master.source_path.nunique() == 2 and master.source_file.nunique() == 1
    assert master.comment_id.nunique() == 6
    dirs = sorted(p for p in (work / "output").iterdir() if p.is_dir())
    assert len(dirs) == 2 and all(d.name.startswith("PRJ_PID_DWG101_RA__") for d in dirs)
    for d in dirs:
        rows = json.loads((d / "comments.json").read_text(encoding="utf-8"))
        status = json.loads((d / "run_status.json").read_text(encoding="utf-8"))
        assert status["status"] == "ok" and len(rows) == 3
        assert {r["source_file_sha256"] for r in rows} == {status["source_file_sha256"]}
        # snapshots in this folder belong to this folder's comments only
        assert sorted(p.stem for p in (d / "images").glob("*.png")) == sorted(r["comment_id"] for r in rows)
    per_file = pd.read_csv(work / "output/master_summary_per_file.csv")
    assert len(per_file) == 2 and per_file.comment_count.tolist() == [3, 3]


def test_single_file_keeps_plain_stem_folder(work, monkeypatch):
    """Contract the PRAJ backend relies on: output/<stem>/comments.json."""
    inp = work / "input"
    make_pdf(inp / "PRJ_PID_DWG101_RA.pdf")
    run_main(work, inp, monkeypatch)
    assert (work / "output/PRJ_PID_DWG101_RA/comments.json").exists()


def test_failed_rerun_leaves_no_stale_results(work, monkeypatch):
    inp = work / "input"
    make_pdf(inp / "PRJ_PID_DWG101_RA.pdf", "one")
    make_pdf(inp / "PRJ_PID_DWG102_RA.pdf", "two")
    run_main(work, inp, monkeypatch)
    out1, out2 = work / "output/PRJ_PID_DWG101_RA", work / "output/PRJ_PID_DWG102_RA"
    assert (out1 / "comments.json").exists() and any((out1 / "images").glob("*.png"))

    real = ce.extract_metadata

    def fail_for_101(doc, filename, llm, cfg):
        if "DWG101" in filename:
            raise RuntimeError("simulated failure")
        return real(doc, filename, llm, cfg)

    monkeypatch.setattr(ce, "extract_metadata", fail_for_101)
    run_main(work, inp, monkeypatch)
    assert not (out1 / "comments.json").exists()                 # no stale "success" left behind
    assert not any((out1 / "images").glob("*.png"))
    status = json.loads((out1 / "run_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed" and "simulated failure" in status["error"]
    assert json.loads((out2 / "run_status.json").read_text(encoding="utf-8"))["status"] == "ok"
    master = pd.read_csv(work / "output/master_comments.csv")
    assert set(master.source_file) == {"PRJ_PID_DWG102_RA.pdf"}  # failed file contributes nothing


# ============================================================ A2 / C6: metadata validation

@pytest.mark.parametrize("token", ["A", "B", "0", "00", "12", "A1", "RA", "R2", "R12", "REV-B",
                                   "REVB", "rev3", "REV.2", "P1", "C02"])
def test_valid_revisions_accepted(token):
    assert ce.plausible_revision(token)


@pytest.mark.parametrize("token", ["PID", "GA", "ISO", "RAW", "SET", "REV", "AA", "R123", "REV-", "Layout", ""])
def test_implausible_revisions_rejected(token):
    assert not ce.plausible_revision(token)


def test_revision_zero_from_filename_is_kept(cfg, work):
    pdf = work / "PRJ_PID_DWG101_0.pdf"
    make_pdf(pdf)
    doc = fitz.open(pdf)
    try:
        m = ce.extract_metadata(doc, pdf.name, None, cfg)
    finally:
        doc.close()
    assert (m["praj_revision"], m["revision_source"]) == ("0", "filename")


def test_drawing_type_code_in_revision_slot_is_not_a_revision(cfg, work):
    pdf = work / "ACME_Layout_A-2301_PID.pdf"
    make_pdf(pdf)
    doc = fitz.open(pdf)
    try:
        m = ce.extract_metadata(doc, pdf.name, None, cfg)
    finally:
        doc.close()
    assert m["drawing_number"] == "A-2301"
    assert (m["praj_revision"], m["revision_source"]) == ("NA", "unresolved")


def _filename_meta(drawing="DWG101", rev="RA"):
    return {"project": "PRJ", "drawing_number": drawing, "praj_revision": rev, "customer_doc": "NA",
            "customer_revision": "NA", "drawing_number_source": "filename" if drawing else None,
            "revision_source": "filename" if rev else None, "metadata_notes": []}


def test_llm_null_like_values_are_ignored():
    m = _filename_meta()
    ce._merge_title_block_values({"drawing_number": "null", "revision": "N/A", "project": None,
                                  "customer_document_number": "unknown", "customer_revision": "-"}, m)
    assert (m["drawing_number"], m["praj_revision"], m["customer_doc"]) == ("DWG101", "RA", "NA")
    assert m["drawing_number_source"] == "filename" and m["metadata_notes"] == []


def test_llm_implausible_values_are_rejected_and_noted():
    m = _filename_meta()
    ce._merge_title_block_values({"drawing_number": "Process and Instrumentation Diagram",
                                  "revision": "Issued for construction", "customer_revision": "LATEST"}, m)
    assert (m["drawing_number"], m["praj_revision"], m["customer_revision"]) == ("DWG101", "RA", "NA")
    assert m["drawing_number_source"] == m["revision_source"] == "filename"
    assert len(m["metadata_notes"]) == 3 and all("rejected" in n for n in m["metadata_notes"])


def test_llm_conflict_is_recorded_and_title_block_wins():
    m = _filename_meta()
    ce._merge_title_block_values({"drawing_number": "DWG-777", "revision": "RB"}, m)
    assert (m["drawing_number"], m["praj_revision"]) == ("DWG-777", "RB")
    assert m["drawing_number_source"] == m["revision_source"] == "title_block_llm"
    assert sum("conflict" in n for n in m["metadata_notes"]) == 2


def test_llm_fills_missing_values_and_keeps_revision_zero():
    m = _filename_meta(drawing=None, rev=None)
    ce._merge_title_block_values({"drawing_number": "4512-P-001", "revision": 0,
                                  "customer_document_number": "CUST-77", "customer_revision": "B",
                                  "unexpected_field": "ignored"}, m)
    assert (m["drawing_number"], m["praj_revision"]) == ("4512-P-001", "0")
    assert m["drawing_number_source"] == m["revision_source"] == "title_block_llm"
    assert (m["customer_doc"], m["customer_revision"]) == ("CUST-77", "B")
    assert m["metadata_notes"] == []


class _FailingLLM:
    def chat_json(self, system, user):
        raise RuntimeError("429")


def test_llm_failure_keeps_filename_metadata_and_notes_it(cfg, work):
    pdf = work / "PRJ_PID_DWG101_RA.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((700, 560), "DWG NO 4512 REV B", fontsize=8)     # title-block text layer
    doc.save(pdf)
    doc = fitz.open(pdf)
    try:
        m = ce.extract_metadata(doc, pdf.name, _FailingLLM(), dataclasses.replace(cfg, metadata_llm_enabled=True))
    finally:
        doc.close()
    assert (m["drawing_number"], m["praj_revision"]) == ("DWG101", "RA")
    assert m["metadata_notes"] == ["title_block_llm: call failed"]


def test_metadata_notes_column_in_output(cfg, work):
    pdf = work / "PRJ_PID_DWG101_RA.pdf"
    make_pdf(pdf)
    _, df = ce.process_pdf(pdf, cfg, None, False)
    assert "metadata_notes" in df.columns and set(df.metadata_notes) == {""}
    assert list(df.columns) == ce.COLUMNS


# ============================================================ A3: rotated-page geometry

def _red_pixels(pix: fitz.Pixmap):
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)
    m = (a[:, :, 0] > 200) & (a[:, :, 1] < 60) & (a[:, :, 2] < 60)
    ys, xs = np.nonzero(m)
    return xs, ys


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_page_geometry_matches_rendered_annotation(cfg, work, rotation):
    """Ground truth = where the annotation is actually DRAWN on the rendered page (red pixels).
    position_key, the id's row segment and the snapshot crop must all agree with it."""
    pdf = work / f"PRJ_PID_DWG101_R{rotation // 90}.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    a = page.add_rect_annot(fitz.Rect(600, 80, 700, 140))      # near the top-right of the unrotated page
    a.set_colors(stroke=(1, 0, 0), fill=(1, 0, 0))
    a.set_info(content="Check nozzle N3 orientation", title="Reviewer")
    a.update()
    page.set_rotation(rotation)
    doc.save(pdf)

    doc = fitz.open(pdf)
    page = doc[0]
    xs, ys = _red_pixels(page.get_pixmap())                    # zoom 1: 1 px == 1 pt, as displayed
    pw, ph = page.rect.width, page.rect.height
    doc.close()
    n = cfg.row_density
    exp_col = int(((xs.min() + xs.max() + 1) / 2) / pw * n)
    exp_row = int(((ys.min() + ys.max() + 1) / 2) / ph * n)
    exp_top_row = int(ys.min() / ph * n)

    _, df = ce.process_pdf(pdf, cfg, None, False)
    assert len(df) == 1
    key = df.position_key.iloc[0]                              # P001-Rrrr-Cccc
    row, col = int(key[6:9]), int(key[11:14])
    assert abs(row - exp_row) <= 1 and abs(col - exp_col) <= 1, (rotation, key, exp_row, exp_col)
    uid_row = int(df.comment_id.iloc[0].split("-")[4])
    assert abs(uid_row - exp_top_row) <= 1, (rotation, uid_row, exp_top_row)
    shot = fitz.Pixmap(str(work / df.snapshot_file.iloc[0]))
    sx, _ = _red_pixels(shot)
    assert len(sx) > 200, f"rotation {rotation}: snapshot does not show the annotation"


def test_title_block_region_follows_the_displayed_page(cfg, work):
    """title_block_region is bottom-right of the page AS DISPLAYED; on a rotated sheet the text
    there must reach the title-block reader (before the fix the clip read the wrong corner)."""
    pdf = work / "PRJ_PID_DWG101_RA.pdf"
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.set_rotation(90)
    page.insert_text(fitz.Point(470, 800) * page.derotation_matrix, "TBMARKER4512", fontsize=10, rotate=90)
    doc.save(pdf)

    seen = {}

    class RecordingLLM:
        def chat_json(self, system, user):
            seen["user"] = user
            return {}

    doc = fitz.open(pdf)
    try:
        ce.extract_metadata(doc, pdf.name, RecordingLLM(), dataclasses.replace(cfg, metadata_llm_enabled=True))
    finally:
        doc.close()
    assert "TBMARKER4512" in seen.get("user", "")

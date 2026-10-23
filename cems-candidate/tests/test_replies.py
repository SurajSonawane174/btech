"""
PDF reply threads (/IRT). Regression tests on synthetic PDFs.

Before this change every reply annotation (e.g. "Agreed, will revise in Rev B" by PRAJ) was
extracted as an independent client comment. Now a reply whose chain reaches an extracted root
is attached to that root (`reply_count`, `replies_json`); replies that cannot be linked safely
are kept as their own comments and flagged in `reply_link_status`.
"""
import dataclasses
import json
import sys
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import comment_extractor as ce  # noqa: E402


@pytest.fixture
def cfg():
    base = ce.Config.from_yaml(ROOT / "config.yaml")
    return dataclasses.replace(base, vision_enabled=False, ocr_enabled=False, enrichment_enabled=False,
                               metadata_llm_enabled=False, classification_llm_enabled=False)


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def note(page, pos, text, author):
    a = page.add_text_annot(pos, text)
    a.set_info(title=author)
    a.update()
    return a


def set_irt(doc, annot_xref, target):
    """target: an xref (int) or a raw PDF value string (for malformed references)."""
    doc.xref_set_key(annot_xref, "IRT", f"{target} 0 R" if isinstance(target, int) else target)


def build(path: Path, wire):
    """wire(doc, page) adds annotations; the PDF is saved and reopened so keys round-trip."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    wire(doc, page)
    doc.save(path)


def collect(path: Path):
    doc = fitz.open(path)
    found = []
    for pno, page in enumerate(doc, start=1):
        f, ok = ce.collect_comments(doc, page, pno)
        assert ok
        found.extend(f)
    return found


def texts(cs):
    return [c["text"] for c in cs]


def test_reply_and_nested_reply_attach_to_root(tmp_path):
    def wire(doc, page):
        root = note(page, (100, 100), "Weld size wrong", "Client")
        r1 = note(page, (100, 100), "Agreed, will revise in Rev B", "PRAJ")
        set_irt(doc, r1.xref, root.xref)
        r2 = note(page, (100, 100), "Please also check weld length", "Client")
        set_irt(doc, r2.xref, r1.xref)                    # reply to the reply
        note(page, (400, 300), "Font too small", "Client")
    build(tmp_path / "t.pdf", wire)
    roots, stats = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert texts(roots) == ["Weld size wrong", "Font too small"]
    assert [r["text"] for r in roots[0]["replies"]] == ["Agreed, will revise in Rev B",
                                                         "Please also check weld length"]
    assert [r["author"] for r in roots[0]["replies"]] == ["PRAJ", "Client"]
    assert roots[1]["replies"] == []
    assert stats["replies_linked"] == 2 and roots[0]["reply_link_status"] == ""


def test_reply_on_another_page_still_links(tmp_path):
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    root = note(doc[0], (100, 100), "Nozzle N3 orientation?", "Client")
    r = note(doc[1], (100, 100), "Rotated 90 deg in Rev C", "PRAJ")
    set_irt(doc, r.xref, root.xref)
    doc.save(tmp_path / "t.pdf")
    roots, stats = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert texts(roots) == ["Nozzle N3 orientation?"]
    assert roots[0]["replies"][0]["page"] == 2 and stats["replies_linked"] == 1


def test_missing_parent_keeps_reply_as_flagged_comment(tmp_path):
    def wire(doc, page):
        r = note(page, (100, 100), "Done as requested", "PRAJ")
        set_irt(doc, r.xref, page.xref)                   # points at the page, not an annotation
        r2 = note(page, (200, 200), "Second orphan", "PRAJ")
        set_irt(doc, r2.xref, 99999)                      # points at nothing
    build(tmp_path / "t.pdf", wire)
    roots, stats = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert texts(roots) == ["Done as requested", "Second orphan"]
    assert {r["reply_link_status"] for r in roots} == {"parent_missing"}
    assert stats["parent_missing"] == 2 and stats["replies_linked"] == 0


def test_reply_to_an_orphan_attaches_to_the_orphan(tmp_path):
    def wire(doc, page):
        orphan = note(page, (100, 100), "Orphan reply", "PRAJ")
        set_irt(doc, orphan.xref, 99999)
        child = note(page, (100, 100), "Follow-up on orphan", "Client")
        set_irt(doc, child.xref, orphan.xref)
    build(tmp_path / "t.pdf", wire)
    roots, stats = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert texts(roots) == ["Orphan reply"]
    assert roots[0]["reply_link_status"] == "parent_missing"
    assert [r["text"] for r in roots[0]["replies"]] == ["Follow-up on orphan"]


def test_malformed_reference_is_kept_and_flagged(tmp_path):
    def wire(doc, page):
        note(page, (300, 300), "A root", "Client")
        r = note(page, (100, 100), "Bad reference", "PRAJ")
        set_irt(doc, r.xref, "(not a reference)")
    build(tmp_path / "t.pdf", wire)
    found = collect(tmp_path / "t.pdf")
    assert any(c["irt_malformed"] for c in found)
    roots, stats = ce.link_replies(found)
    assert texts(roots) == ["A root", "Bad reference"]
    assert roots[1]["reply_link_status"] == "malformed_reference" and stats["malformed_reference"] == 1


def test_cycle_does_not_hang_or_lose_comments(tmp_path):
    def wire(doc, page):
        a = note(page, (100, 100), "Cycle A", "X")
        b = note(page, (200, 200), "Cycle B", "Y")
        c = note(page, (300, 300), "Self loop", "Z")
        set_irt(doc, a.xref, b.xref)
        set_irt(doc, b.xref, a.xref)
        set_irt(doc, c.xref, c.xref)
        d = note(page, (400, 400), "Reply into the cycle", "W")
        set_irt(doc, d.xref, a.xref)
    build(tmp_path / "t.pdf", wire)
    roots, stats = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert sorted(texts(roots)) == sorted(["Cycle A", "Cycle B", "Self loop", "Reply into the cycle"])
    assert {r["reply_link_status"] for r in roots} == {"cycle"} and stats["cycle"] == 4


def test_status_only_reply_linked_and_unlinked(tmp_path):
    def wire(doc, page):
        root = note(page, (100, 100), "Change material to SS316", "Client")
        s = note(page, (100, 100), "", "PRAJ")
        set_irt(doc, s.xref, root.xref)
        doc.xref_set_key(s.xref, "State", "(Accepted)")
        doc.xref_set_key(s.xref, "StateModel", "(Review)")
        lone = note(page, (300, 300), "", "PRAJ")
        set_irt(doc, lone.xref, 99999)
        doc.xref_set_key(lone.xref, "State", "(Rejected)")
        note(page, (500, 500), "", "Nobody")             # empty, no state: skipped as before
    build(tmp_path / "t.pdf", wire)
    roots, stats = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert texts(roots) == ["Change material to SS316"]
    rep = roots[0]["replies"]
    assert len(rep) == 1 and rep[0]["state"] == "Accepted" and rep[0]["text"] == ""
    assert stats["status_markers_unlinked"] == 1


def test_text_reply_under_unlinkable_status_marker_is_not_lost(tmp_path):
    def wire(doc, page):
        s = note(page, (100, 100), "", "PRAJ")
        set_irt(doc, s.xref, 99999)
        doc.xref_set_key(s.xref, "State", "(Completed)")
        child = note(page, (100, 100), "Why completed? Still wrong", "Client")
        set_irt(doc, child.xref, s.xref)
    build(tmp_path / "t.pdf", wire)
    roots, stats = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert texts(roots) == ["Why completed? Still wrong"]
    assert roots[0]["reply_link_status"] == "parent_missing"
    assert stats["status_markers_unlinked"] == 1 and stats["replies_linked"] == 0


def test_group_reply_type_is_recorded(tmp_path):
    def wire(doc, page):
        root = note(page, (100, 100), "Main note", "Client")
        g = note(page, (120, 120), "Grouped note", "Client")
        set_irt(doc, g.xref, root.xref)
        doc.xref_set_key(g.xref, "RT", "/Group")
    build(tmp_path / "t.pdf", wire)
    roots, _ = ce.link_replies(collect(tmp_path / "t.pdf"))
    assert roots[0]["replies"][0]["reply_type"] == "Group"


def _thread_pdf(path: Path):
    def wire(doc, page):
        root = note(page, (100, 100), "Weld size wrong", "Client")
        r = note(page, (100, 100), "Agreed, will revise in Rev B", "PRAJ")
        set_irt(doc, r.xref, root.xref)
        note(page, (400, 300), "Font too small", "Client")
    build(path, wire)


def test_process_pdf_writes_threads_and_run_status(cfg, work):
    pdf = work / "PRJ_DWG300_RA.pdf"
    _thread_pdf(pdf)
    total, df = ce.process_pdf(pdf, cfg, None, False)
    assert total == 2 and list(df.columns) == ce.COLUMNS
    weld = df[df.actual_extracted_comment == "Weld size wrong"].iloc[0]
    assert weld.reply_count == 1 and weld.reply_link_status == ""
    assert json.loads(weld.replies_json)[0]["text"] == "Agreed, will revise in Rev B"
    font = df[df.actual_extracted_comment == "Font too small"].iloc[0]
    assert font.reply_count == 0 and font.replies_json == ""
    status = json.loads((work / "output" / pdf.stem / "run_status.json").read_text())
    assert status["reply_threads"]["replies_linked"] == 1


def test_linking_can_be_disabled_for_previous_behaviour(cfg, work):
    pdf = work / "PRJ_DWG300_RA.pdf"
    _thread_pdf(pdf)
    total, df = ce.process_pdf(pdf, dataclasses.replace(cfg, extraction_link_replies=False), None, False)
    assert total == 3                                    # every annotation is a row, as before
    status = json.loads((work / "output" / pdf.stem / "run_status.json").read_text())
    assert status["reply_threads"] == "linking disabled"


def test_config_flag_parses_strictly(tmp_path):
    import yaml
    y = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    y["extraction"] = {"link_replies": "maybe"}
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(y), encoding="utf-8")
    with pytest.raises(ValueError, match="extraction.link_replies"):
        ce.Config.from_yaml(p)

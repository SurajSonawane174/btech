"""
Mock-based tests for the merged extractor (teammate's OCR path + existing pipeline).
No network, no GPU: the LLM and the OCR engine are fakes with recorded calls.
"""
import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import fitz
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import comment_extractor as ce  # noqa: E402
from local_ocr import clean_ocr_text, parse_box_lines  # noqa: E402


# ---------------------------------------------------------------- fixtures

def make_native_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((60, 300), "PUMP P-101   SECTION A-A", fontsize=10)
    a = page.add_freetext_annot(fitz.Rect(100, 100, 360, 150), "Verify fillet weld size per AWS D1.1")
    a.set_info(title="R. Kulkarni")
    a.update()
    b = page.add_text_annot((500, 200), "Font on the title block is too small")
    b.set_info(title="client.reviewer")
    b.update()
    doc.save(path)


def make_flat_box_pdf(path: Path):
    """A flattened markup: coloured comment box drawn into the page, no annotation objects."""
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((60, 500), "PUMP P-101   SECTION A-A", fontsize=10)
    box = fitz.Rect(400, 120, 640, 230)
    page.draw_rect(box, color=(1.0, 0.85, 0.3), fill=(1.0, 0.9, 0.4))
    page.insert_text((410, 145), "Jane Doe jane@client.com 2026-03-02 10:15", fontsize=8)
    page.insert_text((410, 170), "Increase nozzle N3 to 4in", fontsize=9)
    doc.save(path)


def make_plain_pdf(path: Path):
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((60, 300), "PUMP P-101   SECTION A-A   DWG 4512-R2", fontsize=10)
    doc.save(path)


class FakeLLM:
    """Records calls. vision_parts returns one result per candidate; chat_json routes by prompt."""

    def __init__(self, filter_keep=None, fail_filter=False, enrich=None):
        self.calls = []
        self.filter_keep = filter_keep if filter_keep is not None else []
        self.fail_filter = fail_filter
        self.enrich = enrich or {"is_handwritten": "Y", "visual_feature": "nozzle N3",
                                 "category": "aesthetic", "confidence_percent": 99}

    def chat_json(self, system, user):
        self.calls.append(("chat_json", system))
        if "filter OCR" in system:
            if self.fail_filter:
                raise RuntimeError("429 rate limited")
            return {"keep": self.filter_keep}
        raise AssertionError(f"unexpected chat_json: {system}")

    def chat_vision_json(self, system, user_text, png):
        self.calls.append(("vision_one", system))
        assert png[:4] == b"\x89PNG"
        return dict(self.enrich)

    def chat_vision_parts_json(self, system, parts, max_tokens=1200):
        n = sum(1 for p in parts if p.get("type") == "image_url")
        self.calls.append(("vision_parts", n))
        return {"results": [{"candidate_id": i, "is_comment": True, "author": "Jane Doe",
                             "email": "jane@client.com", "date": "2026-03-02", "time": "10:15",
                             "comment_text": "Increase nozzle N3 to 4in"} for i in range(1, n + 1)]}


class FakeOCR:
    def __init__(self, box_lines=None, page_lines=None):
        self.box_lines = box_lines if box_lines is not None else [
            "Jane Doe jane@client.com 2026-03-02 10:15", "Increase nozzle N3 to 4in"]
        self.page_lines = page_lines if page_lines is not None else [
            "PUMP P-101", "SECTION A-A", "Move pump 200mm east for maintenance access", "DWG 4512-R2"]
        self.rect_calls = 0
        self.page_calls = 0

    def ocr_rect(self, page, rect):
        self.rect_calls += 1
        return list(self.box_lines)

    def ocr_page_lines(self, page):
        self.page_calls += 1
        return list(self.page_lines)


@pytest.fixture
def cfg():
    base = ce.Config.from_yaml(ROOT / "config.yaml")
    return dataclasses.replace(base, vision_enabled=True, ocr_enabled=False, ocr_full_page=False,
                               enrichment_enabled=False, metadata_llm_enabled=False,
                               classification_llm_enabled=False)


@pytest.fixture
def work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # process_pdf writes ./output
    return tmp_path


# ---------------------------------------------------------------- LLM client

def _client_with(cfg, responses, monkeypatch):
    monkeypatch.setenv(cfg.llm_api_key_env, "test-key")
    llm = ce.LLMClient(cfg)
    seq = iter(responses)
    calls = []

    def create(**kw):
        calls.append(kw)
        r = next(seq)
        if isinstance(r, Exception):
            raise r
        return r

    llm.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ce.time, "sleep", lambda s: None)
    return llm, calls


def _resp(content, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content),
                                                    finish_reason=finish)])


def test_retry_means_one_attempt_plus_retries(cfg, monkeypatch):
    llm, calls = _client_with(dataclasses.replace(cfg, llm_max_retries=1),
                              [RuntimeError("502"), _resp('{"ok": 1}')], monkeypatch)
    assert llm.chat_json("s", "u") == {"ok": 1}
    assert len(calls) == 2


def test_zero_retries_raises_the_real_error_not_typeerror(cfg, monkeypatch):
    llm, calls = _client_with(dataclasses.replace(cfg, llm_max_retries=0),
                              [RuntimeError("429 rate limited")], monkeypatch)
    with pytest.raises(RuntimeError, match="429"):
        llm.chat_json("s", "u")
    assert len(calls) == 1


def test_empty_choices_and_empty_content_are_errors(cfg, monkeypatch):
    llm, _ = _client_with(dataclasses.replace(cfg, llm_max_retries=0),
                          [SimpleNamespace(choices=[], error={"message": "upstream down"})], monkeypatch)
    with pytest.raises(RuntimeError, match="no choices"):
        llm.chat_json("s", "u")
    llm, _ = _client_with(dataclasses.replace(cfg, llm_max_retries=0),
                          [_resp(None, finish="length")], monkeypatch)
    with pytest.raises(RuntimeError, match="empty content"):
        llm.chat_json("s", "u")


def test_llm_needed_only_when_a_hosted_feature_is_on(cfg):
    off = dataclasses.replace(cfg, vision_enabled=False)
    assert not off.llm_needed()
    assert not dataclasses.replace(cfg, vision_box_reader="local_ocr").llm_needed()
    assert dataclasses.replace(cfg, vision_box_reader="llm").llm_needed()
    assert dataclasses.replace(off, ocr_enabled=True, ocr_full_page=True, ocr_llm_filter=True).llm_needed()


# ---------------------------------------------------------------- OCR helpers

def test_clean_ocr_text_strips_markup():
    raw = "<div style='x'>\n# Header\n```\n---\nIncrease nozzle N3 to 4in\nab\n"
    assert clean_ocr_text(raw) == ["Header", "Increase nozzle N3 to 4in"]


def test_parse_box_lines_splits_header_from_body():
    p = parse_box_lines(["Jane Doe jane@client.com 2026-03-02 10:15", "Increase nozzle N3 to 4in"])
    assert p == {"author": "Jane Doe", "email": "jane@client.com", "date": "2026-03-02",
                 "time": "10:15", "text": "Increase nozzle N3 to 4in"}
    assert parse_box_lines(["jane@client.com 2026-03-02"]) is None


# ---------------------------------------------------------------- pipeline paths

def test_native_page_never_touches_fallbacks(cfg, work):
    pdf = work / "N.pdf"; make_native_pdf(pdf)
    llm, ocr = FakeLLM(), FakeOCR()
    n, df = ce.process_pdf(pdf, dataclasses.replace(cfg, ocr_enabled=True, ocr_full_page=True),
                           llm, True, ocr=ocr)
    assert n == 2 and set(df.comment_source) == {"native"}
    assert llm.calls == [] and ocr.rect_calls == 0 and ocr.page_calls == 0
    assert list(df.columns) == ce.COLUMNS and "visual_feature" in df.columns


def test_flat_box_read_by_local_ocr_without_any_llm(cfg, work):
    pdf = work / "F.pdf"; make_flat_box_pdf(pdf)
    ocr = FakeOCR()
    c = dataclasses.replace(cfg, vision_box_reader="local_ocr", ocr_enabled=True)
    assert not c.llm_needed()
    n, df = ce.process_pdf(pdf, c, None, False, ocr=ocr)
    assert n == 1 and ocr.rect_calls == 1
    row = df.iloc[0]
    assert row.comment_source == "ocr_box" and row.annotation_type.startswith("OCRBox-")
    assert row.actual_extracted_comment == "Increase nozzle N3 to 4in"
    assert row.email_of_person_commented == "jane@client.com"
    assert pd.isna(row.extraction_confidence_percent)  # no invented score for OCR


def test_flat_box_read_by_hosted_vision_in_one_batched_call(cfg, work):
    pdf = work / "F.pdf"; make_flat_box_pdf(pdf)
    llm = FakeLLM()
    n, df = ce.process_pdf(pdf, cfg, llm, True, ocr=None)
    assert n == 1 and df.iloc[0].comment_source == "vision"
    assert [c for c in llm.calls if c[0] == "vision_parts"] == [("vision_parts", 1)]


def test_hosted_vision_respects_pdf_budget(cfg, work):
    pdf = work / "F.pdf"; make_flat_box_pdf(pdf)
    llm = FakeLLM()
    n, _ = ce.process_pdf(pdf, cfg, llm, False, ocr=None)  # not selected for vision budget
    assert n == 0 and llm.calls == []


def test_full_page_ocr_keeps_only_filtered_lines(cfg, work):
    pdf = work / "P.pdf"; make_plain_pdf(pdf)
    llm, ocr = FakeLLM(filter_keep=[2]), FakeOCR()
    c = dataclasses.replace(cfg, ocr_enabled=True, ocr_full_page=True)
    n, df = ce.process_pdf(pdf, c, llm, False, ocr=ocr)
    assert n == 1 and ocr.page_calls == 1
    assert df.iloc[0].actual_extracted_comment == "Move pump 200mm east for maintenance access"
    assert df.iloc[0].comment_source == "ocr_page"


def test_full_page_ocr_fails_closed_when_filter_fails(cfg, work):
    """Teammate's version kept ALL lines on filter failure (tags/titles become 'comments').
    Merged version: zero comments, transcript goes to review_candidates."""
    pdf = work / "P.pdf"; make_plain_pdf(pdf)
    llm, ocr = FakeLLM(fail_filter=True), FakeOCR()
    c = dataclasses.replace(cfg, ocr_enabled=True, ocr_full_page=True)
    n, _ = ce.process_pdf(pdf, c, llm, False, ocr=ocr)
    assert n == 0
    rc = pd.read_csv(work / "output" / "P" / "review_candidates.csv")
    assert list(rc.reason) == ["ocr_filter_failed"]
    assert (work / "output" / "P" / "review_candidates" / "page_001_ocr_transcript.txt").exists()


def test_full_page_ocr_without_llm_goes_to_review_only(cfg, work):
    pdf = work / "P.pdf"; make_plain_pdf(pdf)
    c = dataclasses.replace(cfg, ocr_enabled=True, ocr_full_page=True)
    n, _ = ce.process_pdf(pdf, c, None, False, ocr=FakeOCR())
    rc = pd.read_csv(work / "output" / "P" / "review_candidates.csv")
    assert n == 0 and list(rc.reason) == ["ocr_unfiltered"]



# ---- unfiltered whole-page OCR: conservative split into per-comment REVIEW candidates ----

STRUCTURED_OCR = [
    "CONTROL VALVE ASSEMBLY & SCANNED CLIENT REVIEW",
    "Client A", "Increase flange thickness to 8 mm", "12-09-2026 14:25",
    "Client B", "Add gasket material note", "12-09-2026 14:25",
    "Reviewer", "Check alignment tolerance", "12-09-2026 14:25",
    "Client C", "Approved after revision", "12-09-2026 14:25",
]


def _review(work):
    import json
    return json.loads((work / "output" / "P" / "review_candidates.json").read_text(encoding="utf-8"))


def test_unfiltered_structured_ocr_becomes_one_review_candidate_per_comment(cfg, work):
    pdf = work / "P.pdf"; make_plain_pdf(pdf)
    c = dataclasses.replace(cfg, ocr_enabled=True, ocr_full_page=True)
    n, df = ce.process_pdf(pdf, c, None, False, ocr=FakeOCR(page_lines=STRUCTURED_OCR))
    assert n == 0 and df.empty                                    # never accepted comments
    rc = _review(work)
    assert [r["candidate_id"] for r in rc] == [f"page_001_ocr_{k:03d}" for k in (1, 2, 3, 4)]
    assert [r["text"] for r in rc] == ["Increase flange thickness to 8 mm", "Add gasket material note",
                                       "Check alignment tolerance", "Approved after revision"]
    assert [r["author"] for r in rc] == ["Client A", "Client B", "Reviewer", "Client C"]
    assert {(r["date"], r["time"]) for r in rc} == {("12-09-2026", "14:25")}   # copied as written
    assert all(r["page"] == 1 and r["status"] == "needs_review" and r["reason"] == "ocr_unfiltered" for r in rc)
    assert not any("approved" in k or "confirmed" in k for r in rc for k in r)
    assert all("CONTROL VALVE ASSEMBLY" not in r["text"] for r in rc)          # title is not a comment
    transcript = work / "output" / "P" / "review_candidates" / "page_001_ocr_transcript.txt"
    assert transcript.read_text(encoding="utf-8") == "\n".join(STRUCTURED_OCR)  # evidence preserved
    assert {r["evidence_file"] for r in rc} == {r["crop_file"] for r in rc} == {
        "output/P/review_candidates/page_001_ocr_transcript.txt"}
    assert [r["evidence_lines"] for r in rc] == ["2-4", "5-7", "8-10", "11-13"]
    csv = pd.read_csv(work / "output" / "P" / "review_candidates.csv")
    assert {"candidate_id", "page", "color", "status", "reason", "crop_file", "text"} <= set(csv.columns)


def test_structured_ocr_after_filter_failure_keeps_filter_failed_reason(cfg, work):
    pdf = work / "P.pdf"; make_plain_pdf(pdf)
    c = dataclasses.replace(cfg, ocr_enabled=True, ocr_full_page=True)
    n, _ = ce.process_pdf(pdf, c, FakeLLM(fail_filter=True), False, ocr=FakeOCR(page_lines=STRUCTURED_OCR))
    rc = _review(work)
    assert n == 0 and len(rc) == 4 and {r["reason"] for r in rc} == {"ocr_filter_failed"}


def test_unstructured_ocr_keeps_single_transcript_candidate(cfg, work):
    pdf = work / "P.pdf"; make_plain_pdf(pdf)
    c = dataclasses.replace(cfg, ocr_enabled=True, ocr_full_page=True)
    n, _ = ce.process_pdf(pdf, c, None, False, ocr=FakeOCR())           # default lines: no blocks
    rc = _review(work)
    assert n == 0 and len(rc) == 1
    assert rc[0]["candidate_id"] == "page_001_ocr" and rc[0]["reason"] == "ocr_unfiltered"
    assert rc[0]["text"] == " | ".join(FakeOCR().page_lines) and "author" not in rc[0]


@pytest.mark.parametrize("lines", [
    ["PUMP P-101", "SECTION A-A", "Move pump 200mm east", "DWG 4512-R2"],               # no timestamps
    ["TITLE", "Client A", "Increase flange thickness", "12-09-2026 14:25"],              # one block only
    STRUCTURED_OCR + ["Approved by PM"],                                                 # text after last block
    ["TITLE", "Client A", "Increase flange", "thickness to 8 mm", "12-09-2026 14:25",    # comment spans 2 lines
     "Client B", "Add gasket note", "12-09-2026 14:25"],
    ["TITLE", "Please increase the flange thickness now", "Do it", "12-09-2026 14:25",   # author line is a sentence
     "Client B", "Add gasket note", "12-09-2026 14:25"],
    ["TITLE", "Client A", "12-09-2026", "12-09-2026 14:25",                              # timestamp in comment slot
     "Client B", "Add gasket note", "12-09-2026 14:25"],
    ["Client A", "12-09-2026 14:25", "Client B", "Add note", "12-09-2026 14:25"],        # first block incomplete
    ["Client A", "Increase flange thickness", "Client B", "12-09-2026 14:25",            # mixed-case line above
     "Client C", "Add gasket note", "12-09-2026 14:25"],                                 #   could be an author
])
def test_ambiguous_ocr_layouts_are_not_split(lines):
    assert ce.split_ocr_comment_blocks(lines) is None


def test_all_caps_title_above_mixed_case_authors_still_splits():
    blocks = ce.split_ocr_comment_blocks(["PUMP SKID LAYOUT", "Client A", "Increase flange thickness", "12-09-2026",
                                          "Client B", "Add gasket note", "12-09-2026"])
    assert [b["author"] for b in blocks] == ["Client A", "Client B"]
    assert all("PUMP SKID" not in b["text"] for b in blocks)


def test_split_keeps_missing_time_as_na_and_never_invents_fields():
    blocks = ce.split_ocr_comment_blocks(["DRAWING TITLE", "J. Mehta", "Add drain valve", "2026-09-12",
                                          "Client B:", "Check flange rating", "12/09/2026 09:05:30"])
    assert blocks == [
        {"author": "J. Mehta", "text": "Add drain valve", "date": "2026-09-12", "time": "NA",
         "first_line": 2, "last_line": 4},
        {"author": "Client B", "text": "Check flange rating", "date": "12/09/2026", "time": "09:05:30",
         "first_line": 5, "last_line": 7},
    ]


def test_enrichment_adds_fields_but_never_overrides_category_or_score(cfg, work):
    pdf = work / "N.pdf"; make_native_pdf(pdf)
    llm = FakeLLM()
    c = dataclasses.replace(cfg, enrichment_enabled=True, enrichment_max_comments=1)
    n, df = ce.process_pdf(pdf, c, llm, False)
    assert len([x for x in llm.calls if x[0] == "vision_one"]) == 1  # cap respected
    first, second = df.iloc[0], df.iloc[1]
    assert first.is_handwritten == "Y" and first.visual_feature == "nozzle N3"
    assert first.comment_category == ce.rule_based_category(first.actual_extracted_comment)
    assert first.extraction_confidence_percent == 100
    assert second.is_handwritten == "N" and second.visual_feature == ""


def test_max_pages_limits_processing(cfg, work):
    pdf = work / "M.pdf"
    doc = fitz.open()
    for i in range(3):
        p = doc.new_page()
        a = p.add_text_annot((100, 100), f"Check item {i}"); a.update()
    doc.save(pdf)
    n, df = ce.process_pdf(pdf, cfg, None, False, max_pages=2)
    assert n == 2 and set(df.page_sheet) == {1, 2}


def test_config_rejects_unknown_box_reader(tmp_path):
    text = (ROOT / "config.yaml").read_text(encoding="utf-8").replace('box_reader: "llm"', 'box_reader: "magic"')
    p = tmp_path / "c.yaml"; p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="box_reader"):
        ce.Config.from_yaml(p)


def test_colab_config_is_local_box_reader_with_full_page_ocr():
    c = ce.Config.from_yaml(ROOT / "config.colab.yaml")
    assert c.vision_box_reader == "local_ocr" and c.ocr_enabled and c.ocr_full_page


# ---------------------------------------------------------------- DB insert carries the new column

def test_insert_comments_bulk_writes_visual_feature(monkeypatch):
    from contextlib import contextmanager
    from database import db
    captured = {}

    class Cur:
        rowcount = 1
        def execute(self, *a): pass
        def fetchone(self): return {"n": 0}      # insert_comments_bulk counts rows with SELECTs

    @contextmanager
    def fake_cursor(commit=False):
        yield Cur()

    def fake_execute_values(cur, sql, rows):
        captured["sql"], captured["rows"] = sql, rows

    monkeypatch.setattr(db, "get_cursor", fake_cursor)
    monkeypatch.setattr(db.psycopg2.extras, "execute_values", fake_execute_values)
    db.insert_comments_bulk("rev-1", [
        {"comment_id": "A-B-001-000-001", "actual_extracted_comment": "x", "visual_feature": "pump P-101"},
        {"comment_id": "A-B-001-000-002", "actual_extracted_comment": "y", "visual_feature": float("nan")},
    ])
    assert "visual_feature" in captured["sql"]
    assert captured["rows"][0][-1] == "pump P-101" and captured["rows"][1][-1] is None

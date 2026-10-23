"""Evaluation harness: metric arithmetic, matching, empty/missing labels, real vs synthetic labelling."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluation import metrics as M  # noqa: E402
from evaluation import run_evaluation as RE  # noqa: E402


def approx(x):
    return pytest.approx(x, abs=1e-9)


# ---------------------------------------------------------------- arithmetic

def test_prf_hand_computed():
    m = M.prf(tp=3, fp=1, fn=2)
    assert m["precision"] == approx(0.75) and m["recall"] == approx(0.6)
    assert m["f1"] == approx(2 * 0.75 * 0.6 / 1.35)


def test_prf_undefined_is_none_not_zero_or_one():
    assert M.prf(0, 0, 0) == {"precision": None, "recall": None, "f1": None, "tp": 0, "fp": 0, "fn": 0}
    m = M.prf(0, 0, 4)                       # nothing predicted
    assert m["precision"] is None and m["recall"] == 0.0 and m["f1"] is None
    assert M.prf(0, 2, 2)["f1"] == 0.0       # both defined and zero


def test_matching_is_one_to_one_and_per_page():
    gold = [{"source_file": "a.pdf", "page": "1", "text": "Weld size wrong"},
            {"source_file": "a.pdf", "page": "1", "text": "Weld size wrong"},
            {"source_file": "a.pdf", "page": "2", "text": "Font too small"}]
    pred = [{"source_file": "a.pdf", "page": "1", "text": "weld  size wrong"},     # whitespace/case only
            {"source_file": "a.pdf", "page": "1", "text": "Font too small"},       # right text, wrong page
            {"source_file": "b.pdf", "page": "2", "text": "Font too small"}]       # wrong file
    assert M.match_comments(pred, gold) == [(0, 0, 100.0)]
    m = M.extraction_metrics(pred, gold)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 2, 2)
    assert m["precision"] == approx(1 / 3) and m["recall"] == approx(1 / 3)


def test_matching_threshold_and_best_pair_first():
    gold = [{"source_file": "a", "page": 1, "text": "Increase nozzle N3 to 4in"},
            {"source_file": "a", "page": 1, "text": "Increase nozzle N3 to 6in"}]
    pred = [{"source_file": "a", "page": 1, "text": "Increase nozzle N3 to 6in"}]
    assert M.match_comments(pred, gold)[0][1] == 1                  # exact beats near-identical
    assert M.match_comments([{"source_file": "a", "page": 1, "text": "Nozzle"}], gold) == []


def test_extraction_empty_cases():
    assert M.extraction_metrics([], [])["status"] == "no_data"
    assert M.extraction_metrics([{"source_file": "a", "page": 1, "text": "x"}], [])["status"] == "no_labels"
    m = M.extraction_metrics([], [{"source_file": "a", "page": 1, "text": "x"}])
    assert m["status"] == "ok" and m["recall"] == 0.0 and m["precision"] is None


def test_classification_accuracy_and_macro_f1():
    pairs = [("technical", "technical"), ("technical", "technical"), ("aesthetic", "technical"),
             ("aesthetic", "aesthetic"), (None, "technical"), ("", "aesthetic")]   # last two unlabelled
    m = M.classification_metrics(pairs)
    assert m["n"] == 4 and m["accuracy"] == approx(0.75)
    # technical: tp2 fp1 fn0 -> f1 0.8 ; aesthetic: tp1 fp0 fn1 -> f1 2/3
    assert m["per_class"]["technical"]["f1"] == approx(0.8)
    assert m["macro_f1"] == approx((0.8 + 2 / 3) / 2)
    assert M.classification_metrics([(None, "x"), ("", "y")])["status"] == "no_labels"


def test_classification_label_never_predicted_counts_as_zero_f1():
    m = M.classification_metrics([("process", "technical"), ("technical", "technical")])
    assert m["per_class"]["process"]["f1"] is None                # 0 predicted, 1 gold: P undefined
    assert m["macro_f1"] == approx((0.0 + 2 / 3) / 2)


def test_duplicate_pairs_from_links_use_connected_components():
    assert M.pairs_from_links([("A", "B"), ("C", "B")]) == {frozenset("AB"), frozenset("BC"), frozenset("AC")}
    gold = M.pairs_from_groups({"g": {"A", "B", "C"}})
    m = M.duplicate_metrics(M.pairs_from_links([("A", "B")]), gold, True)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 0, 2) and m["recall"] == approx(1 / 3)
    assert M.duplicate_metrics(set(), set(), False)["status"] == "no_labels"
    assert M.duplicate_metrics(set(), set(), True)["status"] == "no_data"


def test_retrieval_at_k():
    ranked = {"q1": ["a", "x", "b"], "q2": ["y", "z", "w"], "q3": ["c"]}
    relevant = {"q1": {"a", "b"}, "q2": {"m"}, "q3": set(), "q4": {"d"}}
    m = M.retrieval_metrics(ranked, relevant, k=2)
    # scored: q1 (1 of top2 relevant), q2 (0), q4 (no results). q3 unlabelled -> skipped
    assert m["n"] == 3 and m["queries_skipped_unlabelled"] == 1 and m["queries_without_results"] == 1
    assert m["precision_at_k"] == approx((0.5 + 0 + 0) / 3)
    assert m["recall_at_k"] == approx((0.5 + 0 + 0) / 3)
    assert m["hit_rate_at_k"] == approx(1 / 3)
    assert M.retrieval_metrics(ranked, {"q": set()}, 3)["status"] == "no_labels"
    with pytest.raises(ValueError):
        M.retrieval_metrics(ranked, relevant, 0)


# ---------------------------------------------------------------- harness / formats

def _write(path, rows, cols):
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    return path


PRED_COLS = ["source_file", "page_sheet", "comment_id", "actual_extracted_comment", "comment_category", "duplicate_of"]


def test_evaluate_with_missing_optional_labels(tmp_path):
    gold = _write(tmp_path / "g.csv", [["a.pdf", 1, "NA"]], ["source_file", "page", "comment_text"])
    pred = _write(tmp_path / "p.csv", [["a.pdf", 1, "id1", "NA", "technical", ""]], PRED_COLS)
    m = RE.evaluate(RE.load_gold(gold), RE.load_pred(pred))
    assert m["extraction"]["tp"] == 1                       # literal "NA" text survives as text
    assert m["classification"]["status"] == "no_labels" and m["duplicates"]["status"] == "no_labels"


def test_evaluate_duplicates_only_over_matched_comments(tmp_path):
    gold = _write(tmp_path / "g.csv", [["a.pdf", 1, "Font small", "aesthetic", "d1"],
                                       ["a.pdf", 1, "Font small", "aesthetic", "d1"],
                                       ["a.pdf", 1, "Weld size", "technical", "d2"],
                                       ["a.pdf", 1, "Weld size again", "technical", "d2"]],
                  ["source_file", "page", "comment_text", "category", "duplicate_group"])
    pred = _write(tmp_path / "p.csv", [["a.pdf", 1, "id1", "Font small", "aesthetic", ""],
                                       ["a.pdf", 1, "id2", "Font small", "technical", "id1"],
                                       ["a.pdf", 1, "id3", "Weld size", "technical", ""]], PRED_COLS)
    m = RE.evaluate(RE.load_gold(gold), RE.load_pred(pred))
    assert (m["extraction"]["tp"], m["extraction"]["fn"]) == (3, 1)
    assert m["duplicates"]["tp"] == 1 and m["duplicates"]["gold_pairs_excluded_unmatched"] == 1
    assert m["classification"]["n"] == 3 and m["classification"]["accuracy"] == approx(2 / 3)
    assert m["classification"]["unmatched_gold_with_label"] == 1


def test_bad_formats_fail_loudly(tmp_path):
    with pytest.raises(RE.FormatError, match="comment_text"):
        RE.load_gold(_write(tmp_path / "g.csv", [["a.pdf", 1]], ["source_file", "page"]))
    with pytest.raises(RE.FormatError, match="empty comment_text"):
        RE.load_gold(_write(tmp_path / "g2.csv", [["a.pdf", 1, ""]], ["source_file", "page", "comment_text"]))
    with pytest.raises(RE.FormatError, match="comment_id"):
        RE.load_pred(_write(tmp_path / "p.csv", [["a.pdf", 1, "x"]],
                            ["source_file", "page_sheet", "actual_extracted_comment"]))
    bad = tmp_path / "r.json"
    bad.write_text('["not", "a", "dict"]')
    with pytest.raises(RE.FormatError):
        RE.load_retrieval_results(bad)


def test_templates_match_the_documented_format():
    g = pd.read_csv(ROOT / "evaluation/templates/gold_comments_template.csv")
    r = pd.read_csv(ROOT / "evaluation/templates/gold_retrieval_template.csv")
    assert list(g.columns) == RE.GOLD_REQUIRED + RE.GOLD_OPTIONAL and g.empty
    assert list(r.columns) == RE.RETRIEVAL_REQUIRED and r.empty


def test_report_labels_kind_and_says_real_metrics_unavailable(tmp_path):
    gold = _write(tmp_path / "g.csv", [["a.pdf", 1, "x"]], ["source_file", "page", "comment_text"])
    pred = _write(tmp_path / "p.csv", [["a.pdf", 1, "id1", "x", "technical", ""]], PRED_COLS)
    out = tmp_path / "ev.json"
    rel = _write(tmp_path / "rg.csv", [["weld?", "x"]], RE.RETRIEVAL_REQUIRED)
    res = tmp_path / "rr.json"
    res.write_text(json.dumps({"weld?": ["x", "y"]}))
    r1 = RE.main(["--name", "s", "--kind", "synthetic", "--gold", str(gold), "--pred", str(pred), "--out", str(out),
                  "--retrieval-gold", str(rel), "--retrieval-results", str(res), "--k", "2"])
    assert r1["real_world_metrics"].startswith("unavailable")
    assert r1["datasets"][0]["metrics"]["retrieval"]["recall_at_k"] == 1.0
    r2 = RE.main(["--name", "pilot", "--kind", "real", "--gold", str(gold), "--pred", str(pred), "--out", str(out)])
    assert [d["name"] for d in r2["datasets"]] == ["s", "pilot"] and "pilot" in r2["real_world_metrics"]
    r3 = RE.main(["--name", "s", "--kind", "synthetic", "--gold", str(gold), "--pred", str(pred), "--out", str(out)])
    assert [d["name"] for d in r3["datasets"]] == ["pilot", "s"]          # re-run replaces, does not duplicate
    with pytest.raises(SystemExit):
        RE.main(["--name", "x", "--gold", str(gold), "--pred", str(pred), "--out", str(out)])   # --kind required


def test_synthetic_end_to_end_is_labelled_synthetic(tmp_path, monkeypatch):
    from evaluation import synthetic_eval
    monkeypatch.chdir(tmp_path)
    report = synthetic_eval.main(["--workdir", str(tmp_path / "run"), "--out", str(tmp_path / "ev.json")])
    ds = report["datasets"][0]
    assert ds["kind"] == "synthetic" and report["real_world_metrics"].startswith("unavailable")
    ex = ds["metrics"]["extraction"]
    # 7 gold comments; the PRAJ reply is attached to its parent, so it is not a false positive
    assert (ex["tp"], ex["fp"], ex["fn"]) == (7, 0, 0)
    assert ds["metrics"]["duplicates"]["tp"] == 1
    assert ds["metrics"]["classification"]["status"] == "ok"            # value itself is whatever the rules give

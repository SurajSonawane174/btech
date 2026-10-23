"""
evaluation/synthetic_eval.py -- end-to-end harness check on SYNTHETIC drawings.

Generates two small annotated PDFs whose ground truth is known by construction, runs the real
extractor CLI (offline config: no LLM, no vision, no OCR), writes the gold CSV and scores the
output with run_evaluation.py as dataset kind "synthetic".

What this shows: the harness, the gold format and the native-annotation path work end to end,
and how the rule-based classifier does on these few hand-labelled synthetic sentences.
What it does NOT show: accuracy on real PRAJ drawings. Results are always labelled synthetic.

    python evaluation/synthetic_eval.py [--workdir synthetic_eval_run] [--out evaluation_report.json]
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# (position, text, author, gold category, duplicate group). Categories are the labeller's judgement
# of each sentence, NOT what the rule-based classifier happens to output.
DRAWINGS = {
    "PRJ_PID_DWG901_RA.pdf": [
        ((100, 100), "Verify fillet weld size per AWS D1.1 for the support bracket", "Client", "technical", ""),
        ((300, 160), "Title block font too small to read", "Client", "aesthetic", "font"),
        ((500, 220), "Material of flange F-3 must be SS316", "Client", "technical", ""),
        ((300, 400), "Title block font too small to read", "Client", "aesthetic", "font"),
        ((650, 300), "Revise the title block layout", "Client", "aesthetic", ""),
    ],
    "PRJ_PID_DWG902_RB.pdf": [
        ((120, 120), "Dimension 250 mm missing on section A-A", "Client", "technical", ""),
        ((420, 200), "Align the notes column with the border", "Client", "aesthetic", ""),
    ],
}
# A reply thread on DWG902: the reply is NOT a separate comment in the gold data.
REPLY = ("PRJ_PID_DWG902_RB.pdf", 0, "Added in Rev C", "PRAJ")
OFFLINE_CONFIG_OVERRIDES = {"vision": False, "ocr": False, "enrichment": False}


def make_inputs(workdir: Path) -> Path:
    import fitz
    inp = workdir / "input"
    inp.mkdir(parents=True, exist_ok=True)
    for name, notes in DRAWINGS.items():
        doc = fitz.open()
        page = doc.new_page(width=842, height=595)
        page.insert_text((40, 560), f"synthetic evaluation drawing {name}", fontsize=8)
        annots = []
        for pos, text, author, _, _ in notes:
            a = page.add_text_annot(pos, text)
            a.set_info(title=author)
            a.update()
            annots.append(a.xref)
        if REPLY[0] == name:
            r = page.add_text_annot(notes[REPLY[1]][0], REPLY[2])
            r.set_info(title=REPLY[3])
            r.update()
            doc.xref_set_key(r.xref, "IRT", f"{annots[REPLY[1]]} 0 R")
        doc.save(inp / name)
    return inp


def write_gold(path: Path) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_file", "page", "comment_text", "category", "duplicate_group"])
        for name, notes in DRAWINGS.items():
            for _, text, _, cat, dup in notes:
                w.writerow([name, 1, text, cat, dup])
    return path


def offline_config(workdir: Path) -> Path:
    import yaml
    y = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    y.setdefault("llm", {})["metadata_enabled"] = False
    y.setdefault("classification", {})["llm_enabled"] = False
    for section in ("vision", "ocr", "enrichment"):
        y.setdefault(section, {})["enabled"] = False
    p = workdir / "config.offline.yaml"
    p.write_text(yaml.safe_dump(y), encoding="utf-8")
    return p


def run_extractor(workdir: Path, cfg_path: Path) -> Path:
    import comment_extractor as ce
    old_argv, old_cwd = sys.argv, os.getcwd()
    os.chdir(workdir)
    try:
        sys.argv = ["comment_extractor.py", "--input", "input", "--config", str(cfg_path)]
        ce.main()
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    return workdir / "output" / "master_comments.csv"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workdir", default="synthetic_eval_run")
    ap.add_argument("--out", default=str(ROOT / "evaluation_report.json"))
    args = ap.parse_args(argv)
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    make_inputs(workdir)
    master = run_extractor(workdir, offline_config(workdir))
    gold = write_gold(workdir / "gold_comments.csv")
    from evaluation import run_evaluation
    return run_evaluation.main(["--name", "synthetic-native-v1", "--kind", "synthetic", "--gold", str(gold),
                                "--pred", str(master), "--out", args.out])


if __name__ == "__main__":
    main()

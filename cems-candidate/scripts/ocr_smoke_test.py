"""
scripts/ocr_smoke_test.py -- first REAL check of the local OCR path (LightOnOCR-2-1B).

Until this has been run on real hardware, local OCR is "integrated and unit-tested with a fake
engine" only; nothing has shown that the actual model reads a comment box correctly.

What it does (synthetic, non-confidential input):
  1. builds a flattened markup page: a coloured comment box with header + body text, no PDF
     annotation objects (the case the OCR fallback exists for);
  2. runs the extractor's own colour-box detector on it;
  3. reads the detected box with local_ocr.LocalOCR (the same call the pipeline makes);
  4. parses it with local_ocr.parse_box_lines and compares with the known text
     (RapidFuzz ratio; this is ONE synthetic sample -- a smoke test, not an accuracy figure).

Cost: downloads the model weights on first run (about 2 GB, bf16) plus torch/transformers from
requirements-ocr.txt (CUDA torch is ~2.5 GB). Run on Colab/GPU, not on a metered connection.
It refuses to start without --confirm-download.

    python scripts/ocr_smoke_test.py --confirm-download [--device cuda|cpu|auto]
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BOX_HEADER = "Jane Doe jane@client.com 2026-03-02 10:15"
BOX_BODY = "Increase nozzle N3 to 4in"


def build_page(path: Path):
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((60, 500), "PUMP P-101   SECTION A-A", fontsize=10)
    box = fitz.Rect(400, 120, 640, 230)
    page.draw_rect(box, color=(1.0, 0.85, 0.3), fill=(1.0, 0.9, 0.4))
    page.insert_text((410, 145), BOX_HEADER, fontsize=8)
    page.insert_text((410, 170), BOX_BODY, fontsize=11)
    doc.save(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirm-download", action="store_true",
                    help="allow loading LightOnOCR-2-1B (~2 GB weights on first run)")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--workdir", default="ocr_smoke")
    args = ap.parse_args(argv)
    if not args.confirm_download:
        print("Refusing to run: this loads LightOnOCR-2-1B (~2 GB download on first use). "
              "Re-run with --confirm-download on a GPU machine or Colab.")
        return 2

    import fitz
    import comment_extractor as ce
    from local_ocr import LocalOCR, ocr_available, parse_box_lines
    from rapidfuzz import fuzz

    ok, why = ocr_available()
    if not ok:
        print(f"OCR stack not importable ({why}). Install requirements-ocr.txt first.")
        return 3

    work = Path(args.workdir)
    work.mkdir(exist_ok=True)
    pdf = work / "synthetic_flattened_box.pdf"
    build_page(pdf)
    cfg = ce.Config.from_yaml(ROOT / "config.yaml")
    doc = fitz.open(pdf)
    page = doc[0]
    boxes = ce.detect_color_boxes(page, cfg)
    print(f"colour boxes detected: {len(boxes)}")
    if not boxes:
        print("FAIL: the box detector found nothing; OCR was not exercised.")
        return 1

    engine = LocalOCR(cfg.ocr_model, cfg.ocr_dpi, cfg.ocr_max_new_tokens, cfg.ocr_api_key_env, args.device)
    t0 = time.time()
    lines = engine.ocr_rect(page, boxes[0]["rect"])
    seconds = time.time() - t0
    parsed = parse_box_lines(lines)
    print(f"device: {engine.device}  dtype: {engine.dtype}  seconds (incl. model load): {seconds:.1f}")
    print(f"raw OCR lines: {lines}")
    print(f"parsed: {parsed}")
    if not parsed:
        print("FAIL: OCR produced no usable comment body.")
        return 1
    body_ratio = fuzz.ratio(parsed["text"].lower(), BOX_BODY.lower())
    print(f"body text similarity to ground truth: {body_ratio:.0f}/100 "
          f"(email {'ok' if parsed['email'] == 'jane@client.com' else 'MISSING/WRONG'}, "
          f"date {'ok' if parsed['date'] == '2026-03-02' else 'MISSING/WRONG'})")
    passed = body_ratio >= 90
    print(("PASS" if passed else "FAIL") + " (single synthetic sample: a smoke test, not an accuracy measurement)")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

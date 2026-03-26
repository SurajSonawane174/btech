import os
import re
import json
import logging
import argparse
import time
import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

import fitz  # PyMuPDF
import pandas as pd
from PIL import Image
import pytesseract
from rapidfuzz import fuzz
from tqdm import tqdm
from google import genai
from google.genai import types as genai_types


# ============================
# CONFIG MODEL
# ============================

@dataclass
class ExtractionConfig:
    ocr_enabled: bool
    ocr_dpi: int
    ocr_language: str
    ocr_psm: int
    ocr_confidence_threshold: int
    similarity_threshold: int
    screenshot_margin: float
    screenshot_min_width: int
    screenshot_min_height: int
    gemini_model: str
    row_density: int
    scanned_text_threshold: int


# ============================
# LOGGER
# ============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


# ============================
# DATE PARSER
# ============================

def parse_pdf_date(date_str: str) -> Tuple[str, str]:
    """
    Parse PDF date format: D:YYYYMMDDHHmmSSOHH'mm'
    Returns (date_string, time_string) or ("NA", "NA") on failure.
    """
    if not date_str:
        return "NA", "NA"

    # Strip leading D: if present
    s = date_str.strip()
    if s.startswith("D:"):
        s = s[2:]

    # Must have at least 8 digits for YYYYMMDD
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) < 8:
        return "NA", "NA"

    try:
        year  = digits[0:4]
        month = digits[4:6]
        day   = digits[6:8]
        hour  = digits[8:10]  if len(digits) >= 10 else "00"
        mins  = digits[10:12] if len(digits) >= 12 else "00"
        secs  = digits[12:14] if len(digits) >= 14 else "00"

        date_out = f"{day}/{month}/{year}"
        time_out = f"{hour}:{mins}:{secs}"
        return date_out, time_out
    except Exception:
        return "NA", "NA"


# ============================
# COLOR DETECTION
# ============================

def detect_annotation_color(annot) -> str:
    """
    Detect the dominant color of a PDF annotation.
    Returns a human-readable color name.
    """
    try:
        if not annot.colors:
            return "Unknown"

        stroke = annot.colors.get("stroke")
        fill   = annot.colors.get("fill")
        rgb    = stroke or fill

        if not rgb or not isinstance(rgb, (list, tuple)) or len(rgb) < 3:
            return "Unknown"

        r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])

        # Red
        if r > 0.7 and g < 0.35 and b < 0.35:
            return "Red"
        # Blue
        if b > 0.7 and r < 0.35 and g < 0.5:
            return "Blue"
        # Green
        if g > 0.7 and r < 0.4 and b < 0.4:
            return "Green"
        # Yellow / Orange (often used for highlights)
        if r > 0.8 and g > 0.6 and b < 0.3:
            return "Yellow"
        # Black
        if r < 0.2 and g < 0.2 and b < 0.2:
            return "Black"
        # White
        if r > 0.9 and g > 0.9 and b > 0.9:
            return "White"
        # Magenta / Pink
        if r > 0.7 and b > 0.7 and g < 0.3:
            return "Magenta"

        return f"RGB({round(r*255)},{round(g*255)},{round(b*255)})"

    except Exception:
        return "Unknown"


# ============================
# OCR ENGINE
# ============================

class OCREngine:
    """
    Handles OCR extraction for scanned PDF pages.
    Uses pytesseract with configurable parameters.
    """

    def __init__(self, config: ExtractionConfig):
        self.config = config

    def page_to_image(self, page: fitz.Page) -> Image.Image:
        """Render a PDF page to a PIL Image at the configured DPI."""
        zoom = self.config.ocr_dpi / 72.0
        mat  = fitz.Matrix(zoom, zoom)
        pix  = page.get_pixmap(matrix=mat, alpha=False)
        img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img

    def extract_text_blocks(self, page: fitz.Page) -> List[Dict]:
        """
        Run OCR on a page and return a list of comment blocks.
        Each block: {text, x0, y0, x1, y1, confidence}
        Filters out low-confidence words and groups nearby words into blocks.
        """
        if not self.config.ocr_enabled:
            return []

        try:
            img = self.page_to_image(page)

            # Get word-level data with confidence scores
            custom_config = f"--psm {self.config.ocr_psm} -l {self.config.ocr_language}"
            ocr_data = pytesseract.image_to_data(
                img,
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
            return []

        # Scale factor: OCR coords are at ocr_dpi, page coords are at 72 dpi
        scale = 72.0 / self.config.ocr_dpi

        # Build list of valid words (confidence >= threshold)
        words = []
        n = len(ocr_data["text"])
        for i in range(n):
            conf = ocr_data["conf"][i]
            text = str(ocr_data["text"][i]).strip()

            # Skip empty or low-confidence words
            try:
                conf_int = int(conf)
            except (ValueError, TypeError):
                continue

            if conf_int < self.config.ocr_confidence_threshold or not text:
                continue

            x0 = ocr_data["left"][i]   * scale
            y0 = ocr_data["top"][i]    * scale
            w  = ocr_data["width"][i]  * scale
            h  = ocr_data["height"][i] * scale

            words.append({
                "text": text,
                "x0": x0,
                "y0": y0,
                "x1": x0 + w,
                "y1": y0 + h,
                "conf": conf_int
            })

        if not words:
            return []

        # ---- Group words into comment candidate blocks ----
        # Sort by vertical position first, then horizontal
        words.sort(key=lambda w: (w["y0"], w["x0"]))

        blocks = []
        current_block = [words[0]]

        # Merge words that are within ~10px vertically and ~20px horizontally
        for word in words[1:]:
            prev = current_block[-1]
            vertical_gap   = abs(word["y0"] - prev["y0"])
            horizontal_gap = word["x0"] - prev["x1"]

            if vertical_gap < 12 and horizontal_gap < 30:
                current_block.append(word)
            else:
                blocks.append(current_block)
                current_block = [word]

        blocks.append(current_block)

        # ---- Filter blocks for engineering comment candidates ----
        comment_keywords = {
            "note:", "remark:", "shall:", "must:", "check:", "verify:",
            "ref:", "see:", "revise:", "change:", "correct:", "update:",
            "add:", "remove:", "delete:", "modify:", "review:"
        }

        result = []
        for block in blocks:
            block_text = " ".join(w["text"] for w in block).strip()
            if not block_text:
                continue

            # Accept block if it starts with a known keyword OR is in margin area
            block_lower = block_text.lower()
            first_word  = block_lower.split()[0] if block_lower.split() else ""

            is_keyword_comment = first_word in comment_keywords
            is_margin_comment  = block[0]["x0"] > (page.rect.width * 0.75)

            # Accept blocks with at least 3 words OR keyword/margin comment
            word_count = len(block)
            if word_count >= 3 or is_keyword_comment or is_margin_comment:
                avg_conf = sum(w["conf"] for w in block) / len(block)
                x0 = min(w["x0"] for w in block)
                y0 = min(w["y0"] for w in block)
                x1 = max(w["x1"] for w in block)
                y1 = max(w["y1"] for w in block)

                result.append({
                    "text":       block_text,
                    "x0":         x0,
                    "y0":         y0,
                    "x1":         x1,
                    "y1":         y1,
                    "confidence": round(avg_conf)
                })

        return result


# ============================
# MAIN ENGINE
# ============================

class DrawingReview:

    def __init__(self, config: ExtractionConfig):
        self.config = config
        self.previous_comments: List[str] = []
        self.ocr_engine = OCREngine(config)
        # Initialize Gemini client once per worker (new google-genai SDK)
        self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # --------------------------
    # METADATA EXTRACTION
    # --------------------------

    def extract_metadata(self, doc: fitz.Document, filename: str) -> Dict:
        """
        Extract document metadata from:
        1. Filename parsing (primary)
        2. PDF internal metadata (fallback)
        Expected filename format: PROJECT_SOMETHING_DRAWINGNUMBER_REVISION.pdf
        """
        name  = Path(filename).stem
        parts = name.split("_")

        project        = parts[0] if len(parts) > 0 else "UNKNOWN"
        drawing_number = parts[2] if len(parts) > 2 else "UNKNOWN"
        revision       = parts[3] if len(parts) > 3 else "R0"

        # Fallback: try PDF internal metadata
        pdf_meta = doc.metadata or {}
        customer_doc = "NA"
        customer_rev = "NA"

        # Check PDF metadata fields for customer document info
        subject = pdf_meta.get("subject", "") or ""
        keywords = pdf_meta.get("keywords", "") or ""

        # Try to extract customer doc number from subject/keywords
        # Pattern: "CUST:ABC-123" or "CustomerDoc: XYZ"
        cust_match = re.search(
            r"(?:cust(?:omer)?[\s_\-]?doc[\s_\-]?(?:no|num|number)?|CUST)[:\s]+([A-Z0-9\-]+)",
            subject + " " + keywords,
            re.IGNORECASE
        )
        if cust_match:
            customer_doc = cust_match.group(1).strip()

        return {
            "project":           project,
            "drawing_number":    drawing_number,
            "praj_revision":     revision,
            "customer_doc":      customer_doc,
            "customer_revision": customer_rev
        }

    # --------------------------
    # UNIQUE ID
    # --------------------------

    def get_uid(
        self,
        meta:        Dict,
        page_num:    int,
        rect:        Tuple,
        seq:         int,
        page_height: float
    ) -> str:
        y_pos = rect[1]
        row   = int((y_pos / page_height) * self.config.row_density)

        project = re.sub(r"[^A-Z0-9]", "", meta.get("project", "DOC").upper())
        drawing = re.sub(r"[^A-Z0-9]", "", meta.get("drawing_number", "DWG").upper())

        return f"{project}-{drawing}-{page_num:03d}-{row:03d}-{seq:03d}"

    # --------------------------
    # GEMINI CLASSIFICATION
    # --------------------------

    def classify_comment(self, text: str) -> Tuple[str, int]:
        """
        Returns (category, confidence_percent).
        Stage 1: rapidfuzz similarity check for repeated comments.
        Stage 2: Gemini LLM classification.
        Stage 3: Rule-based fallback on API failure.
        """
        # --- Stage 1: Repeated detection ---
        normalized = text.lower().strip()
        for prev in self.previous_comments:
            if fuzz.ratio(normalized, prev) >= self.config.similarity_threshold:
                return "repeated", 100

        self.previous_comments.append(normalized)

        # --- Stage 2: Gemini LLM ---
        prompt = (
            "Classify the following engineering review comment into exactly one of these categories:\n"
            "- technical   → dimensions, materials, tolerances, code compliance, structural issues\n"
            "- aesthetic   → formatting, labels, colours, typography, visual presentation\n\n"
            f'Comment: "{text}"\n\n'
            "Return ONLY one word: technical or aesthetic"
        )

        try:
            response = self.gemini_client.models.generate_content(
                model=self.config.gemini_model,
                contents=prompt
            )
            result = response.text.strip().lower()

            # Validate response
            if result in ("technical", "aesthetic"):
                return result, 95

            # If Gemini returned something unexpected, fall through to rule-based
            logger.warning(f"Unexpected Gemini response: '{result}' — using rule-based fallback")

        except Exception as e:
            logger.warning(f"Gemini classification failed: {e} — using rule-based fallback")

        # --- Stage 3: Rule-based fallback ---
        return self._rule_based_classify(text)

    def _rule_based_classify(self, text: str) -> Tuple[str, int]:
        """Keyword-based fallback classifier. Returns (category, confidence)."""
        t = text.lower()

        aesthetic_keywords = [
            "font", "colour", "color", "label", "format", "align",
            "spacing", "typo", "text size", "presentation", "layout",
            "heading", "style", "border", "margin", "indent"
        ]
        technical_keywords = [
            "dimension", "material", "tolerance", "weld", "bolt",
            "pressure", "temperature", "load", "stress", "code",
            "standard", "spec", "shall", "must", "remark", "note",
            "verify", "check", "revise", "incorrect", "missing"
        ]

        aesthetic_score = sum(1 for kw in aesthetic_keywords if kw in t)
        technical_score = sum(1 for kw in technical_keywords if kw in t)

        if aesthetic_score > technical_score:
            return "aesthetic", 70
        return "technical", 70  # Default to technical for engineering docs

    # --------------------------
    # SCREENSHOT
    # --------------------------

    def capture_screenshot(
        self,
        page:    fitz.Page,
        rect:    fitz.Rect,
        uid:     str,
        job_dir: Path
    ) -> str:
        """
        Capture a screenshot of the annotation area with context padding.
        Enforces minimum size and boundary clamping as per spec.
        """
        img_dir = job_dir / "images"
        img_dir.mkdir(exist_ok=True)

        page_width  = page.rect.width
        page_height = page.rect.height

        x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
        w = x1 - x0
        h = y1 - y0

        # Apply configurable margin from config (spec: 1.15 default)
        margin_w = w * self.config.screenshot_margin
        margin_h = h * self.config.screenshot_margin

        crop_x0 = max(0, x0 - margin_w)
        crop_y0 = max(0, y0 - margin_h)
        crop_x1 = min(page_width,  x1 + margin_w)
        crop_y1 = min(page_height, y1 + margin_h)

        # Enforce minimum size (spec: 200×150px)
        if (crop_x1 - crop_x0) < self.config.screenshot_min_width:
            extra = (self.config.screenshot_min_width - (crop_x1 - crop_x0)) / 2
            crop_x0 = max(0, crop_x0 - extra)
            crop_x1 = min(page_width, crop_x1 + extra)

        if (crop_y1 - crop_y0) < self.config.screenshot_min_height:
            extra = (self.config.screenshot_min_height - (crop_y1 - crop_y0)) / 2
            crop_y0 = max(0, crop_y0 - extra)
            crop_y1 = min(page_height, crop_y1 + extra)

        crop = fitz.Rect(crop_x0, crop_y0, crop_x1, crop_y1)

        # Render at 150 DPI for quality
        mat = fitz.Matrix(150 / 72, 150 / 72)
        pix = page.get_pixmap(clip=crop, matrix=mat)

        output_path = img_dir / f"{uid}.png"
        pix.save(str(output_path))

        return str(output_path).replace("\\", "/")

    # --------------------------
    # BUILD RECORD
    # --------------------------

    def build_record(
        self,
        sr_no:      int,
        meta:       Dict,
        page_num:   int,
        uid:        str,
        text:       str,
        author:     str,
        date:       str,
        time_val:   str,
        color:      str,
        category:   str,
        confidence: int,
        screenshot: str,
        is_handwritten: str = "N"
    ) -> Dict:
        """Assemble a single comment record matching the required output schema."""
        is_client = (
            "Y"
            if author.lower() not in ["praj", "internal", "unknown", ""]
            else "N"
        )

        return {
            "sr_no":                        sr_no,
            "praj_document_number":         meta["project"],
            "praj_revision_number":         meta.get("praj_revision", "NA"),
            "customer_document_number":     meta.get("customer_doc", "NA"),
            "customer_revision":            meta.get("customer_revision", "NA"),
            "page_sheet":                   page_num,
            "comment_id":                   uid,
            "actual_extracted_comment":     text,
            "snapshot_file":                screenshot,
            "name_of_person_commented":     author,
            "date_of_comment":              date,
            "time_of_comment":              time_val,
            "comment_color":                color,
            "is_client_comment":            is_client,
            "comment_category":             category,
            "is_handwritten":               is_handwritten,
            "extraction_confidence_percent": confidence
        }

    # --------------------------
    # PROCESS PDF
    # --------------------------

    def process_pdf(self, pdf_path: Path) -> int:
        """
        Full processing pipeline for a single PDF.
        Handles both VECTOR (annotation) and SCANNED (OCR) pages.
        """
        job_dir = Path("output") / pdf_path.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        doc  = fitz.open(str(pdf_path))
        meta = self.extract_metadata(doc, pdf_path.name)

        all_data: List[Dict] = []
        seq   = 1
        sr_no = 1

        for page_num in range(len(doc)):
            page         = doc[page_num]
            text_content = page.get_text("text").strip()
            page_type    = (
                "SCANNED"
                if len(text_content) < self.config.scanned_text_threshold
                else "VECTOR"
            )

            logger.info(
                f"{pdf_path.name} | Page {page_num+1} | Type: {page_type}"
            )

            # ==========================================
            # PATH A: VECTOR — native annotation extraction
            # ==========================================
            if page_type == "VECTOR":
                annots = list(page.annots() or [])

                if not annots and self.config.ocr_enabled:
                    # No annotations found on a vector page — try OCR as fallback
                    logger.info(
                        f"No annotations on vector page {page_num+1}, "
                        f"trying OCR fallback"
                    )
                    ocr_blocks = self.ocr_engine.extract_text_blocks(page)
                    for block in ocr_blocks:
                        uid = self.get_uid(
                            meta, page_num + 1,
                            (block["x0"], block["y0"], block["x1"], block["y1"]),
                            seq, page.rect.height
                        )
                        category, conf = self.classify_comment(block["text"])
                        rect = fitz.Rect(
                            block["x0"], block["y0"],
                            block["x1"], block["y1"]
                        )
                        screenshot = self.capture_screenshot(
                            page, rect, uid, job_dir
                        )
                        record = self.build_record(
                            sr_no, meta, page_num + 1, uid,
                            block["text"], "OCR-Detected",
                            "NA", "NA", "Unknown",
                            category, block["confidence"],
                            screenshot
                        )
                        all_data.append(record)
                        seq   += 1
                        sr_no += 1
                    continue

                for annot in annots:
                    text = annot.info.get("content", "").strip()
                    if not text:
                        continue

                    rect = annot.rect

                    uid = self.get_uid(
                        meta, page_num + 1,
                        (rect.x0, rect.y0, rect.x1, rect.y1),
                        seq, page.rect.height
                    )

                    category, confidence = self.classify_comment(text)
                    screenshot = self.capture_screenshot(
                        page, rect, uid, job_dir
                    )

                    # Author
                    author = annot.info.get("title", "").strip() or "Unknown"

                    # Date + Time
                    creation_date_raw = annot.info.get("creationDate", "")
                    date, time_val    = parse_pdf_date(creation_date_raw)

                    # Color
                    color = detect_annotation_color(annot)

                    record = self.build_record(
                        sr_no, meta, page_num + 1, uid,
                        text, author, date, time_val,
                        color, category, confidence, screenshot
                    )
                    all_data.append(record)
                    seq   += 1
                    sr_no += 1

            # ==========================================
            # PATH B: SCANNED — full OCR extraction
            # ==========================================
            else:
                if not self.config.ocr_enabled:
                    logger.info(
                        f"Skipping scanned page {page_num+1} "
                        f"(OCR disabled in config)"
                    )
                    continue

                ocr_blocks = self.ocr_engine.extract_text_blocks(page)
                logger.info(
                    f"OCR found {len(ocr_blocks)} comment blocks "
                    f"on page {page_num+1}"
                )

                for block in ocr_blocks:
                    uid = self.get_uid(
                        meta, page_num + 1,
                        (block["x0"], block["y0"], block["x1"], block["y1"]),
                        seq, page.rect.height
                    )
                    category, conf = self.classify_comment(block["text"])
                    rect = fitz.Rect(
                        block["x0"], block["y0"],
                        block["x1"], block["y1"]
                    )
                    screenshot = self.capture_screenshot(
                        page, rect, uid, job_dir
                    )
                    record = self.build_record(
                        sr_no, meta, page_num + 1, uid,
                        block["text"], "OCR-Detected",
                        "NA", "NA", "Unknown",
                        category, block["confidence"],
                        screenshot
                    )
                    all_data.append(record)
                    seq   += 1
                    sr_no += 1

        doc.close()

        # ---- Save outputs ----
        comments_path = job_dir / "comments.json"
        with open(comments_path, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)

        df = pd.DataFrame(all_data)

        if not df.empty:
            # Full detail CSV
            df.to_csv(job_dir / "final_output.csv", index=False)

            # Summary CSV (per spec: category counts + percentages)
            total = len(df)
            summary_rows = []
            for cat, group in df.groupby("comment_category"):
                count = len(group)
                pct   = round((count / total) * 100, 1)
                summary_rows.append({
                    "Category":   cat,
                    "Count":      count,
                    "Percentage": f"{pct}%"
                })
            summary_rows.append({
                "Category":   "TOTAL",
                "Count":      total,
                "Percentage": "100%"
            })
            pd.DataFrame(summary_rows).to_csv(
                job_dir / "summary.csv", index=False
            )
        else:
            # Write empty files so downstream systems don't break
            pd.DataFrame().to_csv(job_dir / "final_output.csv", index=False)
            pd.DataFrame().to_csv(job_dir / "summary.csv", index=False)

        logger.info(
            f"✓ Processed: {pdf_path.stem} | "
            f"{len(all_data)} comments | "
            f"Output: {job_dir}"
        )

        return len(all_data)


# ============================
# WORKER FUNCTION
# ============================

def worker(pdf_path: Path, config: ExtractionConfig) -> Tuple[str, int]:
    """
    Worker entry point for ProcessPoolExecutor.
    Each worker gets its own DrawingReview instance (and Gemini client).
    """
    try:
        engine = DrawingReview(config)
        count  = engine.process_pdf(pdf_path)
        return pdf_path.name, count
    except Exception as e:
        logger.error(f"Worker failed for {pdf_path.name}: {e}")
        return pdf_path.name, 0


# ============================
# MAIN
# ============================

def main():
    parser = argparse.ArgumentParser(
        description="Engineering Comment Extraction & Classification Engine"
    )
    parser.add_argument(
        "--input", required=True,
        help="PDF file, folder, or glob pattern (e.g. drawings/*.pdf)"
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Number of parallel workers (default: cpu_count - 1)"
    )

    BASE_DIR       = Path(__file__).resolve().parent
    DEFAULT_CONFIG = BASE_DIR / "config.yaml"
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))

    args = parser.parse_args()

    # ---- Load YAML config ----
    config_path = Path(args.config)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Please create config.yaml — see config.yaml.example"
        )

    with open(config_path, encoding="utf-8") as f:
        yaml_config = yaml.safe_load(f)

    config = ExtractionConfig(
        ocr_enabled                = yaml_config["ocr"]["enabled"],
        ocr_dpi                    = yaml_config["ocr"]["dpi"],
        ocr_language               = yaml_config["ocr"].get("language", "eng"),
        ocr_psm                    = yaml_config["ocr"].get("psm", 6),
        ocr_confidence_threshold   = yaml_config["ocr"].get(
                                        "confidence_threshold", 50),
        similarity_threshold       = yaml_config["classification"][
                                        "similarity_threshold"],
        screenshot_margin          = yaml_config["screenshot"]["margin"],
        screenshot_min_width       = yaml_config["screenshot"].get(
                                        "min_width", 200),
        screenshot_min_height      = yaml_config["screenshot"].get(
                                        "min_height", 150),
        gemini_model               = yaml_config["classification"]["gemini_model"],
        row_density                = yaml_config.get("uid", {}).get(
                                        "row_density", 80),
        scanned_text_threshold     = yaml_config.get(
                                        "scanned_text_threshold", 50)
    )

    # ---- Validate Gemini API key is set ----
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set.\n"
            "Create a .env file or set it in your shell:\n"
            "  Windows PowerShell: $env:GEMINI_API_KEY = 'your_key_here'\n"
            "  Mac/Linux:          export GEMINI_API_KEY=your_key_here"
        )

    # ---- Collect PDF files ----
    input_path = Path(args.input)
    pdf_files: List[Path] = []

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        pdf_files.append(input_path)
    elif input_path.is_dir():
        pdf_files = sorted(input_path.glob("**/*.pdf"))
    else:
        # Glob pattern
        from glob import glob
        pdf_files = [Path(p) for p in glob(str(args.input))]

    if not pdf_files:
        logger.warning(f"No PDF files found at: {args.input}")
        return

    logger.info(f"Found {len(pdf_files)} PDF file(s) to process")

    # ---- Determine worker count ----
    max_workers = args.workers or max(1, (os.cpu_count() or 2) - 1)

    # ---- Process ----
    start    = time.time()
    results  = {}

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(worker, pdf, config): pdf
            for pdf in pdf_files
        }
        for future in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Processing PDFs"
        ):
            name, count = future.result()
            results[name] = count

    elapsed = round(time.time() - start, 2)

    # ---- Final summary ----
    total_comments = sum(results.values())
    logger.info("=" * 50)
    logger.info(f"Completed in {elapsed}s")
    logger.info(f"Total PDFs processed : {len(pdf_files)}")
    logger.info(f"Total comments found : {total_comments}")
    for name, count in results.items():
        logger.info(f"  {name}: {count} comments")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()

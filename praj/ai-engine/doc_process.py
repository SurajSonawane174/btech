import os
import re
import json
import logging
import argparse
import time
import yaml
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

import fitz
import pandas as pd
from PIL import Image
import pytesseract
from rapidfuzz import fuzz
from tqdm import tqdm
import google.generativeai as genai


# ============================
# CONFIG MODEL
# ============================

@dataclass
class ExtractionConfig:
    ocr_enabled: bool
    ocr_dpi: int
    similarity_threshold: int
    screenshot_margin: float
    gemini_model: str


# ============================
# LOGGER
# ============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)


# ============================
# MAIN ENGINE
# ============================

class DrawingReview:

    def __init__(self, config: ExtractionConfig):
        self.config = config
        self.previous_comments = []

    # --------------------------
    # METADATA EXTRACTION
    # --------------------------

    def extract_metadata(self, doc, filename):

        meta = doc.metadata

        project = meta.get("title") or Path(filename).stem

        return {
            "project": project,
            "praj_revision": "R0",
            "customer_doc": "NA",
            "customer_revision": "NA"
        }


    # --------------------------
    # UNIQUE ID
    # --------------------------

    def get_uid(self, meta, page_num, rect, seq, page_height):
        row = int((rect[1] / page_height) * 80)
        doc_name = meta.get("project", "DOC")

        return f"{doc_name}-{page_num:03d}-{row:03d}-{seq:03d}"



    # --------------------------
    # GEMINI CLASSIFICATION
    # --------------------------

    def classify_comment(self, text: str) -> str:

        for prev in self.previous_comments:
            if fuzz.ratio(prev, text) >= self.config.similarity_threshold:
                return "repeated"

        self.previous_comments.append(text)

        prompt = f"""
        Classify the following engineering review comment into:
        - technical
        - aesthetic

        Comment: "{text}"

        Return only one word.
        """

        try:
            model = genai.GenerativeModel(self.config.gemini_model)
            response = model.generate_content(prompt)
            return response.text.strip().lower()
        except Exception as e:
            logger.warning(f"Gemini classification failed: {e}")
            return "technical"

    # --------------------------
    # SCREENSHOT
    # --------------------------

    def capture_screenshot(self, page, rect, uid, job_dir):

        img_dir = job_dir / "images"
        img_dir.mkdir(exist_ok=True)

        x0, y0, x1, y1 = rect
        page_width = page.rect.width
        page_height = page.rect.height

        # Expand significantly for engineering context
        horizontal_expand = page_width * 0.25
        vertical_expand = page_height * 0.25

        crop = fitz.Rect(
            max(0, x0 - horizontal_expand),
            max(0, y0 - vertical_expand),
            min(page_width, x1 + horizontal_expand),
            min(page_height, y1 + vertical_expand)
        )

        pix = page.get_pixmap(clip=crop)
        output_path = img_dir / f"{uid}.png"
        pix.save(str(output_path))

        return str(output_path)


    # --------------------------
    # PROCESS PDF
    # --------------------------

    def process_pdf(self, pdf_path: Path):

        job_dir = Path("output") / pdf_path.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(pdf_path)
        meta = self.extract_metadata(doc, pdf_path.name)

        all_data = []
        seq = 1
        sr_no = 1

        for page_num in range(len(doc)):

            page = doc[page_num]
            text_content = page.get_text("text").strip()
            page_type = "SCANNED" if len(text_content) < 50 else "VECTOR"

            if page_type == "VECTOR":
                for annot in page.annots() or []:

                    text = annot.info.get("content", "").strip()
                    if not text:
                        continue

                    rect = annot.rect

                    uid = self.get_uid(
                        meta,
                        page_num + 1,
                        (rect.x0, rect.y0, rect.x1, rect.y1),
                        seq,
                        page.rect.height
                    )

                    category = self.classify_comment(text)
                    screenshot = self.capture_screenshot(page, rect, uid, job_dir)

                    # -----------------------------
                    # Extract Author + Date + Time
                    # -----------------------------

                    author = annot.info.get("title", "Unknown")

                    creation_date = annot.info.get("creationDate", "")
                    date = "NA"
                    time_val = "NA"

                    # -----------------------------
                    # Comment Color Detection
                    # -----------------------------

                    color = "Unknown"

                    if annot.colors and annot.colors.get("stroke"):
                        rgb = annot.colors["stroke"]

                        if rgb[0] > 0.8 and rgb[1] < 0.2:
                            color = "Red"
                        elif rgb[2] > 0.8:
                            color = "Blue"

                    # -----------------------------
                    # Client Comment Logic
                    # -----------------------------

                    is_client = "Y" if author.lower() not in ["praj", "internal"] else "N"

                    # -----------------------------
                    # Handwritten Detection
                    # -----------------------------

                    handwritten = "N"

                    # -----------------------------
                    # Extraction Confidence
                    # -----------------------------

                    confidence = 100

                    # -----------------------------
                    # FINAL RECORD STRUCTURE
                    # -----------------------------

                    record = {
                        "sr_no": sr_no,
                        "praj_document_number": meta["project"],
                        "praj_revision_number": meta.get("praj_revision", "NA"),
                        "customer_document_number": meta.get("customer_doc", "NA"),
                        "customer_revision": meta.get("customer_revision", "NA"),
                        "page_sheet": page_num + 1,
                        "comment_id": uid,
                        "actual_extracted_comment": text,
                        "snapshot_file": screenshot,
                        "name_of_person_commented": author,
                        "date_of_comment": date,
                        "time_of_comment": time_val,
                        "comment_color": color,
                        "is_client_comment": is_client,
                        "comment_category": category,
                        "is_handwritten": handwritten,
                        "extraction_confidence_percent": confidence
                    }

                    all_data.append(record)

                    seq += 1
                    sr_no += 1

                    if not text:
                        continue

                    rect = annot.rect
                    uid = self.get_uid(meta, page_num+1,
                                       (rect.x0, rect.y0, rect.x1, rect.y1),
                                       seq, page.rect.height)

                    category = self.classify_comment(text)
                    screenshot = self.capture_screenshot(
                        page, rect, uid, job_dir)

                    all_data.append({
                        "uid": uid,
                        "text": text,
                        "category": category,
                        "page": page_num+1,
                        "screenshot": screenshot
                    })

                    seq += 1

        # Save JSON
        with open(job_dir / "comments.json", "w") as f:
            json.dump(all_data, f, indent=4)

        # Save CSV summary
        df = pd.DataFrame(all_data)
        if not df.empty:
            df = pd.DataFrame(all_data)
            df.to_csv(job_dir / "final_output.csv", index=False)    

        df = pd.DataFrame(all_data)

        if not df.empty:
            df.to_csv(job_dir / "final_output.csv", index=False)


        logger.info(f"Processed {pdf_path.name} with {len(all_data)} comments")

        return len(all_data)


# ============================
# WORKER FUNCTION
# ============================

def worker(pdf_path: Path, config: ExtractionConfig):
    engine = DrawingReview(config)
    return engine.process_pdf(pdf_path)


# ============================
# MAIN
# ============================

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True,
                        help="PDF file or folder")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    # Load YAML config
    with open(args.config) as f:
        yaml_config = yaml.safe_load(f)

    config = ExtractionConfig(
        ocr_enabled=yaml_config["ocr"]["enabled"],
        ocr_dpi=yaml_config["ocr"]["dpi"],
        similarity_threshold=yaml_config["classification"]["similarity_threshold"],
        screenshot_margin=yaml_config["screenshot"]["margin"],
        gemini_model=yaml_config["classification"]["gemini_model"]
    )

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    input_path = Path(args.input)

    pdf_files = []

    if input_path.is_file():
        pdf_files.append(input_path)
    else:
        pdf_files = list(input_path.glob("*.pdf"))

    start = time.time()

    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker, pdf, config)
                   for pdf in pdf_files]

        for future in tqdm(as_completed(futures),
                           total=len(futures),
                           desc="Processing PDFs"):
            future.result()

    end = time.time()

    logger.info(f"Completed in {round(end-start, 2)} seconds")


if __name__ == "__main__":
    main()

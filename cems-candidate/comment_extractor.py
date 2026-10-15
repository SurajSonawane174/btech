"""
Engineering drawing comment extractor.

Pipeline (one document at a time, page by page):
  1. Metadata   : filename + title-block text layer -> hosted LLM -> JSON
  2. Comments   : native PDF annotations via PyMuPDF (text, author, date, colour, box, callout arrow)
                  -> if a page has ZERO native annotations, fall back to:
  2b. Fallback  : detect coloured comment-box regions on the rendered page (no model), then read
                  each box with either a hosted vision LLM (vision.box_reader: llm) or local
                  LightOnOCR (box_reader: local_ocr, on-prem). No boxes at all -> optional
                  whole-page local OCR whose lines become comments only after an LLM filter.
  2c. Enrich    : optional per-snapshot vision pass -> is_handwritten + visual_feature
  3. Repeats    : fuzzy de-duplication across the whole document (no LLM call)
  4. Classify   : one hosted-LLM call per page (chunked) -> technical / aesthetic
  5. Screenshot : crop around the comment box AND its callout arrow target
  6. Output     : per-PDF comments.json / final_output.csv / summary.csv
                  + a master_comments.csv/json and master_summary.csv across every PDF run

The LLM is any OpenAI-compatible endpoint serving an open-source model
(Hugging Face Inference Providers, Together, Fireworks, OpenRouter, ...).
Configure it in config.yaml; the API token comes from an environment variable.
For the vision fallback you need a multimodal-capable model on that same
(or a separate) OpenAI-compatible endpoint.
"""

import argparse
import base64
import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import numpy as np
import pandas as pd
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from rapidfuzz import fuzz, process
from scipy import ndimage
from tqdm import tqdm

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("comment_extractor")


# ============================
# CONFIG
# ============================

DEFAULT_BOX_COLORS = {
    # name -> approximate RGB (0-255) of the box fill. These are pastel/light fills
    # (comment box interiors), not the saturated colors you'd picture for "red" etc.
    # Sample your own docs' actual fills if boxes go undetected -- see the color-probe
    # snippet in the accompanying notes.
    "Yellow": (255, 230, 101),
    "Blue": (180, 230, 255),
    "Red": (254, 200, 200),
    "Purple": (230, 200, 254),
    "Green": (200, 255, 200),
}


@dataclass
class Config:
    llm_base_url: str
    llm_model: str
    llm_api_key_env: str
    llm_batch_size: int
    llm_max_workers: int
    llm_timeout: int
    llm_max_retries: int
    metadata_llm_enabled: bool
    classification_llm_enabled: bool
    vision_max_pdfs: int
    title_block_region: Tuple[float, float, float, float]
    similarity_threshold: int
    screenshot_margin: float
    screenshot_min_width: int
    screenshot_min_height: int
    screenshot_dpi: int
    row_density: int
    # vision fallback
    vision_enabled: bool
    vision_mode: str                       # "generic" (color-agnostic, recommended) or "palette" (fixed target colors)
    vision_model: str
    vision_base_url: str
    vision_api_key_env: str
    vision_render_dpi: int
    vision_box_min_width_pt: float
    vision_box_min_height_pt: float
    vision_dilate_px: int
    # generic mode
    vision_min_spread: int                 # min (max-min) channel difference to count as "colorful", not gray
    vision_min_value: int                  # min brightness floor, excludes near-black text/lines
    vision_max_area_fraction: float        # skip components bigger than this fraction of the page (backgrounds/washes)
    vision_min_fill_density: float         # matched-pixel fraction within bbox, filters thin lines/leaders
    # palette mode (legacy, only used when vision_mode == "palette")
    vision_color_tolerance: int = 40
    vision_colors: Dict[str, Tuple[int, int, int]] = field(default_factory=lambda: dict(DEFAULT_BOX_COLORS))
    # who reads a detected box: "llm" (hosted vision model) or "local_ocr" (LightOnOCR, on-prem)
    vision_box_reader: str = "llm"
    # local OCR (LightOnOCR-2-1B), see local_ocr.py
    ocr_enabled: bool = False
    ocr_model: str = "lightonai/LightOnOCR-2-1B"
    ocr_api_key_env: str = "HF_TOKEN"
    ocr_dpi: int = 150
    ocr_max_new_tokens: int = 2048
    ocr_device: str = "auto"
    ocr_full_page: bool = False            # last resort when a page has no annotations AND no boxes
    ocr_llm_filter: bool = True            # whole-page OCR lines only become comments after this filter
    # per-comment snapshot enrichment (hosted vision): is_handwritten + visual_feature
    enrichment_enabled: bool = False
    enrichment_max_comments: int = 50

    def llm_needed(self) -> bool:
        """True when any enabled feature calls the hosted LLM (so an API key is required)."""
        return (self.metadata_llm_enabled or self.classification_llm_enabled
                or (self.vision_enabled and self.vision_box_reader == "llm")
                or (self.ocr_enabled and self.ocr_full_page and self.ocr_llm_filter)
                or self.enrichment_enabled)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        with open(path, encoding="utf-8") as f:
            y = yaml.safe_load(f)
        llm = y["llm"]
        shot = y.get("screenshot", {})
        vis = y.get("vision", {})
        ocr = y.get("ocr", {}) or {}
        enr = y.get("enrichment", {}) or {}
        if vis.get("box_reader", "llm") not in ("llm", "local_ocr"):
            raise ValueError("vision.box_reader must be 'llm' or 'local_ocr'")
        colors = dict(DEFAULT_BOX_COLORS)
        colors.update({k: tuple(v) for k, v in vis.get("colors", {}).items()})
        return cls(
            llm_base_url=llm["base_url"],
            llm_model=llm["model"],
            llm_api_key_env=llm.get("api_key_env", "LLM_API_KEY"),
            llm_batch_size=llm.get("batch_size", 40),
            llm_max_workers=llm.get("max_workers", 4),
            llm_timeout=llm.get("timeout", 90),
            llm_max_retries=llm.get("max_retries", 2),
            metadata_llm_enabled=llm.get("metadata_enabled", True),
            classification_llm_enabled=y.get("classification", {}).get("llm_enabled", False),
            vision_max_pdfs=vis.get("max_pdfs", 5),
            title_block_region=tuple(y.get("title_block", {}).get("region", [0.5, 0.7, 1.0, 1.0])),
            similarity_threshold=y.get("classification", {}).get("similarity_threshold", 90),
            screenshot_margin=shot.get("margin", 1.15),
            screenshot_min_width=shot.get("min_width", 200),
            screenshot_min_height=shot.get("min_height", 150),
            screenshot_dpi=shot.get("dpi", 150),
            row_density=y.get("uid", {}).get("row_density", 80),
            vision_enabled=vis.get("enabled", False),
            vision_mode=vis.get("mode", "generic"),
            vision_model=vis.get("model", llm["model"]),
            vision_base_url=vis.get("base_url", llm["base_url"]),
            vision_api_key_env=vis.get("api_key_env", llm.get("api_key_env", "LLM_API_KEY")),
            vision_render_dpi=vis.get("render_dpi", 200),
            vision_box_min_width_pt=vis.get("box_min_width_pt", 100),
            vision_box_min_height_pt=vis.get("box_min_height_pt", 50),
            vision_dilate_px=vis.get("dilate_px", 4),
            vision_min_spread=vis.get("min_spread", 25),
            vision_min_value=vis.get("min_value", 50),
            vision_max_area_fraction=vis.get("max_area_fraction", 0.18),
            vision_min_fill_density=vis.get("min_fill_density", 0.25),
            vision_color_tolerance=vis.get("color_tolerance", 40),
            vision_colors=colors,
            vision_box_reader=vis.get("box_reader", "llm"),
            ocr_enabled=ocr.get("enabled", False),
            ocr_model=ocr.get("model", "lightonai/LightOnOCR-2-1B"),
            ocr_api_key_env=ocr.get("api_key_env", "HF_TOKEN"),
            ocr_dpi=ocr.get("dpi", 150),
            ocr_max_new_tokens=ocr.get("max_new_tokens", 2048),
            ocr_device=ocr.get("device", "auto"),
            ocr_full_page=ocr.get("full_page", False),
            ocr_llm_filter=ocr.get("llm_filter", True),
            enrichment_enabled=enr.get("enabled", False),
            enrichment_max_comments=enr.get("max_comments", 50),
        )


# ============================
# HELPERS
# ============================

def parse_pdf_date(date_str: str) -> Tuple[str, str]:
    """PDF date 'D:YYYYMMDDHHmmSS...' -> ('DD/MM/YYYY', 'HH:MM:SS') or ('NA','NA')."""
    if not date_str:
        return "NA", "NA"
    s = date_str.strip()
    if s.startswith("D:"):
        s = s[2:]
    digits = re.sub(r"[^0-9]", "", s)
    if len(digits) < 8:
        return "NA", "NA"
    hour = digits[8:10] if len(digits) >= 10 else "00"
    mins = digits[10:12] if len(digits) >= 12 else "00"
    secs = digits[12:14] if len(digits) >= 14 else "00"
    return f"{digits[6:8]}/{digits[4:6]}/{digits[0:4]}", f"{hour}:{mins}:{secs}"


def detect_annotation_color(annot) -> str:
    """Human-readable name of the annotation's stroke/fill colour."""
    try:
        colors = annot.colors or {}
        rgb = colors.get("stroke") or colors.get("fill")
        if not rgb or len(rgb) < 3:
            return "Unknown"
        r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
        if r > 0.7 and g < 0.35 and b < 0.35:
            return "Red"
        if b > 0.7 and r < 0.35 and g < 0.5:
            return "Blue"
        if g > 0.7 and r < 0.4 and b < 0.4:
            return "Green"
        if r > 0.8 and g > 0.6 and b < 0.3:
            return "Yellow"
        if r < 0.2 and g < 0.2 and b < 0.2:
            return "Black"
        if r > 0.9 and g > 0.9 and b > 0.9:
            return "White"
        if r > 0.7 and b > 0.7 and g < 0.3:
            return "Magenta"
        return f"RGB({round(r*255)},{round(g*255)},{round(b*255)})"
    except Exception:
        return "Unknown"


def extract_json(text: str):
    """Pull the first JSON object/array out of an LLM reply (tolerates fences and <think> blocks)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("No JSON found in model reply")
    obj, _ = json.JSONDecoder().raw_decode(text[min(starts):])
    return obj


# ============================
# LLM CLIENT (OpenAI-compatible, hosted open-source model)
# ============================

class LLMClient:
    def __init__(self, cfg: Config):
        key = os.getenv(cfg.llm_api_key_env)
        if not key:
            raise EnvironmentError(
                f"{cfg.llm_api_key_env} is not set. Put it in .env or export it in your shell."
            )
        self.client = OpenAI(base_url=cfg.llm_base_url, api_key=key, timeout=cfg.llm_timeout, max_retries=0)
        self.model = cfg.llm_model
        self.max_retries = cfg.llm_max_retries

        # Vision client may point at a different endpoint/model; falls back to the same creds.
        vkey = os.getenv(cfg.vision_api_key_env) or key
        self.vision_client = OpenAI(base_url=cfg.vision_base_url, api_key=vkey, timeout=cfg.llm_timeout, max_retries=0)
        self.vision_model = cfg.vision_model

    @staticmethod
    def _content(resp, model: str) -> str:
        """Reply text, or raise with the provider's real error (OpenRouter returns 200 with
        no choices on some upstream failures; an empty reply must not parse as 'no data')."""
        if not getattr(resp, "choices", None):
            err = getattr(resp, "error", None) or (getattr(resp, "model_extra", None) or {}).get("error") or resp
            raise RuntimeError(f"Provider returned no choices for model '{model}': {err}")
        content = resp.choices[0].message.content
        if not content:
            raise RuntimeError(f"Model '{model}' returned empty content "
                               f"(finish_reason={resp.choices[0].finish_reason})")
        return content

    def _complete_json(self, client, model: str, messages: list, max_tokens: int, label: str):
        """One call path for every request: 1 attempt + max_retries retries, backoff only
        between attempts, and the real last error re-raised (never `raise None`)."""
        attempts = max(0, self.max_retries) + 1
        last: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                resp = client.chat.completions.create(
                    model=model, messages=messages, temperature=0, max_tokens=max_tokens)
                return extract_json(self._content(resp, model))
            except Exception as e:  # network, rate limit, empty reply, bad JSON ...
                last = e
                if attempt < attempts:
                    wait = 2 ** (attempt - 1)
                    logger.warning(f"{label} call failed ({e}); retry {attempt}/{attempts - 1} in {wait}s")
                    time.sleep(wait)
        raise last  # type: ignore[misc]

    def chat_json(self, system: str, user: str):
        return self._complete_json(
            self.client, self.model,
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=2000, label="LLM")

    def chat_vision_json(self, system: str, user_text: str, image_png_bytes: bytes):
        """Same retry/JSON-extraction contract as chat_json, but attaches one image."""
        b64 = base64.b64encode(image_png_bytes).decode("ascii")
        return self._complete_json(
            self.vision_client, self.vision_model,
            [{"role": "system", "content": system},
             {"role": "user", "content": [
                 {"type": "text", "text": user_text},
                 {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
             ]}],
            max_tokens=500, label="Vision LLM")

    def chat_vision_parts_json(self, system: str, parts: list, max_tokens: int = 1200):
        """Multi-image request (several box crops in one call), same retry contract."""
        return self._complete_json(
            self.vision_client, self.vision_model,
            [{"role": "system", "content": system}, {"role": "user", "content": parts}],
            max_tokens=max_tokens, label="Vision batch")


# ============================
# METADATA
# ============================

# Plausibility rules. Deliberately conservative: a value that fails is left unresolved
# rather than guessed (e.g. "Annotation" is not a drawing number, "Set" is not a revision).
_RE_PROJECT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{1,19}$")
_RE_DRAWING = re.compile(r"^(?=.*\d)[A-Za-z0-9][A-Za-z0-9./-]{1,39}$")      # must contain a digit
_RE_REVISION = re.compile(r"^(?:REV|R|P|C)?[-.]?[A-Z0-9]{1,2}$", re.I)     # RA, R2, REV-B, B, 0, P1


def plausible_project(v: Optional[str]) -> bool:
    return bool(v) and bool(_RE_PROJECT.match(v))


def plausible_drawing(v: Optional[str]) -> bool:
    return bool(v) and bool(_RE_DRAWING.match(v))


def plausible_revision(v: Optional[str]) -> bool:
    return bool(v) and bool(_RE_REVISION.match(v))


def parse_filename(filename: str) -> Dict:
    """
    Expected: PROJECT_SOMETHING_DRAWINGNUMBER_REVISION.pdf. Each part is kept only if it
    passes its plausibility check; otherwise it is None (resolved later or left unresolved).
    """
    parts = Path(filename).stem.split("_")
    project = parts[0] if len(parts) > 0 else None
    drawing = parts[2] if len(parts) > 2 else None
    revision = parts[3] if len(parts) > 3 else None
    return {
        "project": project if plausible_project(project) else None,
        "drawing_number": drawing if plausible_drawing(drawing) else None,
        "praj_revision": revision if plausible_revision(revision) else None,
        "customer_doc": "NA",
        "customer_revision": "NA",
    }


_DOCINFO_DRAWING = re.compile(r"(?:DWG|Drawing|Doc(?:ument)?)\s*(?:No\.?|Number|#)?\s*[:=]\s*([A-Za-z0-9./-]+)", re.I)
_DOCINFO_REVISION = re.compile(r"\bRev(?:ision)?\.?\s*[:=]\s*([A-Za-z0-9.-]+)", re.I)


def parse_pdf_docinfo(info: Dict) -> Dict:
    """
    Drawing/revision from the PDF's own metadata, accepted ONLY when explicitly labelled
    (e.g. title 'Drawing No: DWG-4512, Rev: B'). An unlabelled title is not used: titles are
    often free text set by the authoring tool, and a guess here would become a fake identity.
    """
    text = " | ".join(str(info.get(k) or "") for k in ("title", "subject", "keywords"))
    out: Dict[str, Optional[str]] = {"drawing_number": None, "praj_revision": None}
    m = _DOCINFO_DRAWING.search(text)
    if m and plausible_drawing(m.group(1).rstrip(".,;")):
        out["drawing_number"] = m.group(1).rstrip(".,;")
    m = _DOCINFO_REVISION.search(text)
    if m and plausible_revision(m.group(1).rstrip(".,;")):
        out["praj_revision"] = m.group(1).rstrip(".,;")
    return out


def extract_metadata(doc: fitz.Document, filename: str, llm: LLMClient, cfg: Config) -> Dict:
    """
    Resolve document metadata with explicit provenance, never inventing values:
      1. title block via LLM (only when metadata_enabled and a text layer exists)
      2. filename parts that pass plausibility checks
      3. labelled values in the PDF's own metadata (title / subject / keywords)
      4. otherwise unresolved -> drawing 'UNKNOWN', revision 'NA'
    meta['drawing_number_source'] / meta['revision_source'] record which step won.
    """
    meta = parse_filename(filename)
    meta["drawing_number_source"] = "filename" if meta["drawing_number"] else None
    meta["revision_source"] = "filename" if meta["praj_revision"] else None
    _apply_title_block(doc, meta, llm, cfg)
    _apply_pdf_docinfo(doc, meta)
    if not meta["project"]:
        meta["project"] = "UNKNOWN"
    if not meta["drawing_number"]:
        meta["drawing_number"], meta["drawing_number_source"] = "UNKNOWN", "unresolved"
    if not meta["praj_revision"]:
        meta["praj_revision"], meta["revision_source"] = "NA", "unresolved"
    if "unresolved" in (meta["drawing_number_source"], meta["revision_source"]):
        logger.warning(f"{filename}: drawing={meta['drawing_number']} ({meta['drawing_number_source']}), "
                       f"revision={meta['praj_revision']} ({meta['revision_source']}); "
                       f"ids from this file are told apart from other files only by the {UID_HASH_HEX}-hex "
                       f"file-hash suffix (probabilistic, not a uniqueness guarantee); "
                       f"set drawing/revision before ingest")
    return meta


def _apply_pdf_docinfo(doc: fitz.Document, meta: Dict) -> None:
    """Fill ONLY still-missing drawing/revision from labelled PDF metadata fields."""
    found = parse_pdf_docinfo(doc.metadata or {})
    for key, src_key in (("drawing_number", "drawing_number_source"), ("praj_revision", "revision_source")):
        if not meta[key] and found.get(key):
            meta[key], meta[src_key] = found[key], "pdf_metadata"


def _apply_title_block(doc: fitz.Document, meta: Dict, llm: Optional[LLMClient], cfg: Config) -> None:
    """Title-block LLM read (unchanged prompt). Values it returns override the filename."""
    if len(doc) == 0:
        return

    page = doc[0]
    r = page.rect
    x0, y0, x1, y1 = cfg.title_block_region
    clip = fitz.Rect(
        r.x0 + r.width * x0, r.y0 + r.height * y0,
        r.x0 + r.width * x1, r.y0 + r.height * y1,
    )
    tb_text = page.get_text("text", clip=clip).strip()[:4000]
    if not tb_text:
        logger.info("Title block has no text layer; using filename / PDF metadata only")
        return
    if not cfg.metadata_llm_enabled or llm is None:
        logger.info("Metadata LLM disabled; using filename / PDF metadata only")
        return

    system = "You extract fields from engineering drawing title blocks. Reply with JSON only."
    user = (
        "Below is raw text from the title block of an engineering drawing.\n"
        "Return a JSON object with exactly these keys (use null if a value is not present):\n"
        '  "project"                  - project name or code\n'
        '  "drawing_number"           - the issuing company\'s own drawing/document number\n'
        '  "revision"                 - the issuing company\'s revision of this drawing\n'
        '  "customer_document_number" - the customer\'s / client\'s document number\n'
        '  "customer_revision"        - the customer\'s revision\n'
        "Do not guess. Copy values exactly as written.\n\n"
        f"Title block text:\n{tb_text}"
    )
    try:
        data = llm.chat_json(system, user)
        if isinstance(data, dict):
            def clean(v):
                return str(v).strip() if v not in (None, "", "null") else None

            for key, field_name in [
                ("project", "project"),
                ("drawing_number", "drawing_number"),
                ("revision", "praj_revision"),
                ("customer_document_number", "customer_doc"),
                ("customer_revision", "customer_revision"),
            ]:
                v = clean(data.get(key))
                if v:
                    meta[field_name] = v
                    if field_name == "drawing_number":
                        meta["drawing_number_source"] = "title_block_llm"
                    elif field_name == "praj_revision":
                        meta["revision_source"] = "title_block_llm"
    except Exception as e:
        logger.warning(f"Title-block extraction failed, keeping filename metadata: {e}")


# ============================
# COMMENT COLLECTION (native annotations)
# ============================

SKIP_TYPES = {"Link", "Widget", "Popup"}


def callout_points(doc: fitz.Document, page: fitz.Page, annot) -> List[fitz.Point]:
    """
    Callout-line vertices (/CL) of a FreeText callout, converted to page coordinates.
    Best effort: anything that lands outside the page is dropped.
    """
    try:
        kind, val = doc.xref_get_key(annot.xref, "CL")
        if kind != "array":
            return []
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", val)]
        m = page.transformation_matrix * page.rotation_matrix
        pts = [fitz.Point(nums[i], nums[i + 1]) * m for i in range(0, len(nums) - 1, 2)]
        bounds = page.rect + (-50, -50, 50, 50)
        return [p for p in pts if bounds.contains(p)]
    except Exception:
        return []


class AnnotationExtractionError(RuntimeError):
    """Raised when PyMuPDF cannot safely iterate a page's native annotations."""


def collect_comments(doc: fitz.Document, page: fitz.Page, page_no: int) -> Tuple[List[Dict], bool]:
    """Collect native annotations and explicitly report whether iteration completed.

    Important: an annotation-iteration exception is NOT the same thing as an empty page.
    The old implementation returned the partial list and the caller interpreted it as
    "no annotations", which could silently trigger the expensive vision fallback.
    """
    out: List[Dict] = []
    try:
        annots_iter = page.annots() or []
    except Exception as e:
        logger.error(f"Native annotation extraction failed to start on page {page_no}: {e}")
        return out, False

    try:
        for annot in annots_iter:
            atype = annot.type[1]
            if atype in SKIP_TYPES:
                continue

            info = annot.info
            text = (info.get("content") or "").strip()

            if not text and atype == "FreeText":
                text = page.get_text("text", clip=annot.rect).strip()
            if not text:
                continue

            date, time_val = parse_pdf_date(info.get("creationDate") or info.get("modDate") or "")
            out.append({
                "page": page_no,
                "text": re.sub(r"\s+", " ", text),
                "author": (info.get("title") or "").strip() or "Unknown",
                "email": "",
                "date": date,
                "time": time_val,
                "color": detect_annotation_color(annot),
                "rect": fitz.Rect(annot.rect),
                "arrow_pts": callout_points(doc, page, annot),
                "annot_type": atype,
                "source": "native",
            })
    except Exception as e:
        logger.error(
            f"Native annotation extraction failed during iteration on page {page_no}: {e}. "
            f"Discarding {len(out)} partial native comment(s) rather than treating the page as empty."
        )
        return [], False
    return out, True


# ============================
# COMMENT COLLECTION (vision fallback for flattened/rasterized pages)
# ============================

def _color_mask(rgb_arr: np.ndarray, target: Tuple[int, int, int], tolerance: int) -> np.ndarray:
    # int32, not int16: squared channel diffs (up to 255^2*3) overflow int16.
    diff = rgb_arr.astype(np.int32) - np.array(target, dtype=np.int32)
    dist = np.sqrt((diff ** 2).sum(axis=-1))
    return dist <= tolerance


def _hue_name(r: int, g: int, b: int) -> str:
    """Bucket name for logging only -- detection itself clusters on raw hue degrees,
    not on this name, so mislabeling here never affects what gets detected."""
    mx, mn = max(r, g, b), min(r, g, b)
    if mx - mn < 15:
        return "Gray"
    h = float(_hue_degrees(np.array([[r, g, b]], dtype=np.int32))[0])
    if h < 15 or h >= 345:
        return "Red"
    if h < 45:
        return "Orange"
    if h < 70:
        return "Yellow"
    if h < 170:
        return "Green"
    if h < 255:
        return "Blue"
    if h < 320:
        return "Purple"
    return "Pink"


def _hue_degrees(rgb: np.ndarray) -> np.ndarray:
    """Vectorized RGB (int32, ..., 3) -> hue in degrees [0,360). Undefined (gray) pixels
    get hue 0, but callers only use this where the colorfulness mask is already True."""
    r, g, b = rgb[..., 0].astype(np.float64), rgb[..., 1].astype(np.float64), rgb[..., 2].astype(np.float64)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    delta = np.where(mx - mn == 0, 1.0, mx - mn)  # avoid /0; result unused where mx==mn anyway
    hue = np.zeros_like(mx)
    is_r = (mx == r)
    is_g = (mx == g) & ~is_r
    is_b = (mx == b) & ~is_r & ~is_g
    hue[is_r] = (60 * (((g[is_r] - b[is_r]) / delta[is_r]) % 6))
    hue[is_g] = (60 * (((b[is_g] - r[is_g]) / delta[is_g]) + 2))
    hue[is_b] = (60 * (((r[is_b] - g[is_b]) / delta[is_b]) + 4))
    return hue % 360


def _iou(a: fitz.Rect, b: fitz.Rect) -> float:
    inter = a & b
    if inter.is_empty:
        return 0.0
    inter_area = inter.width * inter.height
    union_area = a.width * a.height + b.width * b.height - inter_area
    return inter_area / union_area if union_area > 0 else 0.0


def detect_color_boxes_generic(page: fitz.Page, cfg: Config) -> List[Dict]:
    """
    Hue-clustered, not a fixed palette: groups pixels by hue FAMILY (e.g. "reddish",
    "bluish") rather than exact RGB, so a saturated header strip and its lighter pastel
    body (same hue family, different lightness) merge into one box automatically --
    without a fixed target-color list. Pixels are only clustered with same-hue
    neighbours, so the detector won't bridge two genuinely different-colored boxes
    through unrelated scattered colored elements elsewhere on the drawing (which a
    fully color-agnostic "any non-gray pixel" mask would do on a busy CAD drawing).
    Filters out: tiny icons (min size), whole-page tinted backgrounds (max area
    fraction), and thin colored lines/leader arrows (fill density).
    """
    zoom = cfg.vision_render_dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    rgb = arr[:, :, :3].astype(np.int32)

    spread = rgb.max(axis=-1) - rgb.min(axis=-1)
    value = rgb.max(axis=-1)
    colorful = (spread >= cfg.vision_min_spread) & (value >= cfg.vision_min_value)
    if not colorful.any():
        return []
    hue = _hue_degrees(rgb)

    struct = np.ones((3, 3), dtype=bool)
    page_area_pt = page.rect.width * page.rect.height
    bin_width, overlap, n_bins = 45.0, 12.0, 8
    half = bin_width / 2 + overlap

    candidates: List[Dict] = []
    for i in range(n_bins):
        center = i * bin_width
        hue_dist = np.minimum(np.abs(hue - center), 360 - np.abs(hue - center))
        bin_mask = colorful & (hue_dist <= half)
        if not bin_mask.any():
            continue
        dilated = ndimage.binary_dilation(bin_mask, structure=struct, iterations=cfg.vision_dilate_px) if cfg.vision_dilate_px > 0 else bin_mask
        labeled, n = ndimage.label(dilated, structure=struct)
        if n == 0:
            continue
        for obj in ndimage.find_objects(labeled):
            if obj is None:
                continue
            y0, y1 = obj[0].start, obj[0].stop
            x0, x1 = obj[1].start, obj[1].stop
            px0, py0, px1, py1 = x0 / zoom, y0 / zoom, x1 / zoom, y1 / zoom
            w, h = px1 - px0, py1 - py0
            if w < cfg.vision_box_min_width_pt or h < cfg.vision_box_min_height_pt:
                continue
            if (w * h) > cfg.vision_max_area_fraction * page_area_pt:
                continue
            sub = bin_mask[y0:y1, x0:x1]
            density = sub.mean()
            if density < cfg.vision_min_fill_density:
                continue
            mean_rgb = rgb[y0:y1, x0:x1][sub].mean(axis=0)
            candidates.append({
                "rect": fitz.Rect(px0, py0, px1, py1),
                "color": _hue_name(int(mean_rgb[0]), int(mean_rgb[1]), int(mean_rgb[2])),
                "area": w * h,
            })

    # overlapping hue bins can find the same box twice -- keep the larger, drop overlaps
    candidates.sort(key=lambda c: -c["area"])
    kept: List[Dict] = []
    for c in candidates:
        if not any(_iou(c["rect"], k["rect"]) > 0.3 for k in kept):
            kept.append(c)
    for c in kept:
        del c["area"]
    return kept


def detect_color_boxes_palette(page: fitz.Page, cfg: Config) -> List[Dict]:
    """Legacy fixed-palette matcher (vision.mode: 'palette'). Only useful when you know
    the exact box colors in advance and want to avoid any false positives from generic
    detection -- otherwise prefer detect_color_boxes_generic."""
    zoom = cfg.vision_render_dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    rgb = arr[:, :, :3]

    boxes: List[Dict] = []
    struct = np.ones((3, 3), dtype=bool)
    for color_name, target_rgb in cfg.vision_colors.items():
        mask = _color_mask(rgb, target_rgb, cfg.vision_color_tolerance)
        if cfg.vision_dilate_px > 0:
            mask = ndimage.binary_dilation(mask, structure=struct, iterations=cfg.vision_dilate_px)
        labeled, n = ndimage.label(mask, structure=struct)
        if n == 0:
            continue
        objs = ndimage.find_objects(labeled)
        for obj in objs:
            if obj is None:
                continue
            y0, y1 = obj[0].start, obj[0].stop
            x0, x1 = obj[1].start, obj[1].stop
            px0, py0, px1, py1 = x0 / zoom, y0 / zoom, x1 / zoom, y1 / zoom
            w, h = px1 - px0, py1 - py0
            if w < cfg.vision_box_min_width_pt or h < cfg.vision_box_min_height_pt:
                continue
            boxes.append({"rect": fitz.Rect(px0, py0, px1, py1), "color": color_name})
    return boxes


def detect_color_boxes(page: fitz.Page, cfg: Config) -> List[Dict]:
    if cfg.vision_mode == "palette":
        return detect_color_boxes_palette(page, cfg)
    return detect_color_boxes_generic(page, cfg)


def render_candidate_crop(page: fitz.Page, rect: fitz.Rect, cfg: Config) -> bytes:
    pad = 8
    crop = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad) & page.rect
    zoom = cfg.vision_render_dpi / 72.0
    pix = page.get_pixmap(clip=crop, matrix=fitz.Matrix(zoom, zoom))
    return pix.tobytes("png")


def read_boxes_with_vision(llm: LLMClient, page: fitz.Page, boxes: List[Dict], cfg: Config) -> Dict[int, Dict]:
    """Send several visual candidates in ONE multimodal request."""
    if not boxes:
        return {}
    parts = [{"type": "text", "text": (
        "You are reading review-comment boxes from an engineering drawing. "
        "Each image below is one candidate. Return JSON only in this exact shape: "
        '{"results":[{"candidate_id":1,"is_comment":true,"author":null,"email":null,'
        '"date":null,"time":null,"comment_text":"..."}]}\n'
        "For each candidate, copy visible comment text verbatim. Do not guess. "
        "If it is not a review comment, set is_comment=false and comment_text=null. "
        "Include every candidate_id exactly once.\n\n"
    )}]
    crops = {}
    for i, box in enumerate(boxes, start=1):
        crops[i] = render_candidate_crop(page, box["rect"], cfg)
        parts.append({"type": "text", "text": f"CANDIDATE_ID={i}"})
        b64 = base64.b64encode(crops[i]).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    try:
        data = llm.chat_vision_parts_json(
            "Read engineering drawing review-comment images and return strict JSON only.", parts)
        rows = data.get("results", []) if isinstance(data, dict) else []
        out = {}
        for row in rows:
            try:
                cid = int(row.get("candidate_id"))
            except Exception:
                continue
            if cid < 1 or cid > len(boxes) or not row.get("is_comment"):
                continue
            text = (row.get("comment_text") or "").strip()
            if not text:
                continue
            out[cid] = {
                "author": str(row.get("author") or "Unknown").strip(),
                "email": str(row.get("email") or "").strip(),
                "date": str(row.get("date") or "NA").strip(),
                "time": str(row.get("time") or "NA").strip(),
                "text": re.sub(r"\s+", " ", text),
            }
        return out
    except Exception as e:
        logger.warning(f"Vision batch failed for {len(boxes)} candidate(s): {e}")
        return {}


def read_boxes_with_local_ocr(ocr, page: fitz.Page, boxes: List[Dict]) -> Dict[int, Dict]:
    """On-prem box reader: LightOnOCR on each detected box crop, header fields by regex."""
    from local_ocr import parse_box_lines
    out: Dict[int, Dict] = {}
    for i, box in enumerate(boxes, start=1):
        try:
            parsed = parse_box_lines(ocr.ocr_rect(page, box["rect"]))
        except Exception as e:
            logger.warning(f"Local OCR failed for box {i} at {box['rect']}: {e}")
            continue
        if parsed:
            out[i] = parsed
    return out


def _boxes_to_comments(page: fitz.Page, page_no: int, boxes: List[Dict], parsed: Dict[int, Dict],
                       cfg: Config, review_dir: Path, source: str, reason: str) -> Tuple[List[Dict], List[Dict]]:
    out, review = [], []
    prefix = "VisionDetected" if source == "vision" else "OCRBox"
    for i, box in enumerate(boxes, start=1):
        candidate_id = f"page_{page_no:03d}_candidate_{i:03d}"
        crop_path = review_dir / f"{candidate_id}.png"
        crop_path.write_bytes(render_candidate_crop(page, box["rect"], cfg))
        if i not in parsed:
            review.append({
                "candidate_id": candidate_id, "page": page_no, "color": box["color"],
                "status": "needs_review", "reason": reason,
                "crop_file": str(crop_path).replace("\\", "/"), "text": "",
            })
            continue
        p = parsed[i]
        out.append({
            "page": page_no, "text": p["text"], "author": p["author"],
            "email": p["email"], "date": p["date"], "time": p["time"],
            "color": box["color"], "rect": box["rect"], "arrow_pts": [],
            "annot_type": f"{prefix}-{box['color']}", "source": source,
        })
    return out, review


FILTER_SYSTEM = "You filter OCR output from engineering drawings. Reply with JSON only."


def filter_ocr_segments(llm: LLMClient, segments: List[str], chunk: int = 60) -> Optional[List[str]]:
    """Keep only lines that read as review comments. Returns None if ANY chunk fails:
    the caller then sends the page to review instead of guessing (fail closed)."""
    kept: List[str] = []
    for k in range(0, len(segments), chunk):
        part = segments[k:k + chunk]
        payload = [{"id": i, "text": t} for i, t in enumerate(part)]
        user = (
            "Below are text lines OCR'd from ONE page of an engineering drawing.\n"
            "Keep ONLY lines that are review comments: an instruction, change, request, observation or check "
            "(e.g. \"Increase diameter to 70mm\", \"Move pump 200mm\", \"Change valve to 4in\"). "
            "They may contain numbers, units or symbols.\n"
            "Drop: equipment tags / IDs / part numbers / drawing numbers (e.g. MS045I, V-102, PT-102), "
            "titles, labels, legends, plain dimensions, title-block text and ordinary drawing text.\n\n"
            'Return JSON only: {"keep": [<ids of lines to keep>]}\n\n'
            f"Lines:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        try:
            data = llm.chat_json(FILTER_SYSTEM, user)
            ids = data.get("keep", []) if isinstance(data, dict) else data
            for i in ids:
                i = int(i)
                if 0 <= i < len(part):
                    kept.append(part[i])
        except Exception as e:
            logger.warning(f"OCR comment filter failed ({e}); page goes to review, not into comments")
            return None
    return kept


def ocr_full_page(page: fitz.Page, page_no: int, ocr, llm: Optional[LLMClient], cfg: Config,
                  review_dir: Path) -> Tuple[List[Dict], List[Dict]]:
    """Last resort: whole-page OCR. Lines become comments only after a successful LLM
    filter; otherwise the transcript is saved for human review. No box location exists,
    so the page itself is the snapshot."""
    try:
        lines = ocr.ocr_page_lines(page)
    except Exception as e:
        logger.error(f"Page {page_no}: full-page OCR failed: {e}")
        return [], []
    if not lines:
        return [], []
    kept = filter_ocr_segments(llm, lines) if (llm is not None and cfg.ocr_llm_filter) else None
    if kept is None:
        transcript = review_dir / f"page_{page_no:03d}_ocr_transcript.txt"
        transcript.write_text("\n".join(lines), encoding="utf-8")
        reason = "ocr_unfiltered" if (llm is None or not cfg.ocr_llm_filter) else "ocr_filter_failed"
        return [], [{"candidate_id": f"page_{page_no:03d}_ocr", "page": page_no, "color": "",
                     "status": "needs_review", "reason": reason,
                     "crop_file": str(transcript).replace("\\", "/"), "text": " | ".join(lines)[:2000]}]
    logger.info(f"Page {page_no}: full-page OCR read {len(lines)} line(s), kept {len(kept)} as comments")
    return [{
        "page": page_no, "text": re.sub(r"\s+", " ", t), "author": "Unknown", "email": "",
        "date": "NA", "time": "NA", "color": "Unknown", "rect": fitz.Rect(page.rect),
        "arrow_pts": [], "annot_type": "OCRPage", "source": "ocr_page",
    } for t in kept], []


def fallback_page(page: fitz.Page, page_no: int, llm: Optional[LLMClient], cfg: Config,
                  review_dir: Path, vision_allowed: bool, ocr=None) -> Tuple[List[Dict], List[Dict], str]:
    """
    Recovery for a page with no native annotations (or a failed native read).
      1. detect coloured comment boxes locally (no model)
      2. read them with the hosted vision LLM, or with local OCR (vision.box_reader)
      3. no boxes at all -> whole-page local OCR, if ocr.full_page is on
    Returns (comments, review_candidates, path_used).
    """
    boxes = detect_color_boxes(page, cfg) if cfg.vision_enabled else []
    if boxes:
        if cfg.vision_box_reader == "local_ocr":
            if ocr is None:
                return [], [], "boxes_no_reader"
            parsed = read_boxes_with_local_ocr(ocr, page, boxes)
            found, review = _boxes_to_comments(page, page_no, boxes, parsed, cfg, review_dir,
                                               "ocr_box", "ocr_no_valid_result")
            return found, review, "ocr_box"
        if vision_allowed and llm is not None:
            parsed = read_boxes_with_vision(llm, page, boxes, cfg)
            found, review = _boxes_to_comments(page, page_no, boxes, parsed, cfg, review_dir,
                                               "vision", "vision_no_valid_result")
            return found, review, "vision"
        return [], [], "boxes_no_reader"
    if ocr is not None and cfg.ocr_full_page:
        found, review = ocr_full_page(page, page_no, ocr, llm, cfg, review_dir)
        return found, review, "ocr_page"
    return [], [], "none"


# ============================
# CLASSIFICATION
# ============================

VALID_CATEGORIES = {"technical", "aesthetic"}

CLASSIFY_SYSTEM = (
    "You classify review comments written on engineering drawings. Reply with JSON only."
)

AESTHETIC_KW = ["font", "colour", "color", "label", "format", "align", "spacing", "typo",
                "text size", "presentation", "layout", "heading", "style", "border",
                "margin", "indent"]
TECHNICAL_KW = ["dimension", "material", "tolerance", "weld", "bolt", "pressure",
                "temperature", "load", "stress", "code", "standard", "spec", "shall",
                "must", "remark", "note", "verify", "check", "revise", "incorrect",
                "missing"]


def rule_based_category(text: str) -> str:
    t = text.lower()
    a = sum(k in t for k in AESTHETIC_KW)
    b = sum(k in t for k in TECHNICAL_KW)
    return "aesthetic" if a > b else "technical"


def classify_batch(llm: LLMClient, batch: List[Tuple[int, str]]) -> Dict[int, Tuple[str, str]]:
    """batch = [(comment_index, text)] -> {comment_index: (category, method)}"""
    payload = [{"id": i, "text": t} for i, t in batch]
    user = (
        "Classify each engineering drawing review comment as exactly one of:\n"
        "- technical: dimensions, materials, tolerances, code/standard compliance, process, "
        "structural or design issues, missing or incorrect data\n"
        "- aesthetic: formatting, labels, fonts, colours, typography, alignment, "
        "visual presentation\n\n"
        'Return JSON only: {"results": [{"id": <id>, "category": "technical" or "aesthetic"}]}\n'
        "Include every id exactly once.\n\n"
        f"Comments:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    out: Dict[int, Tuple[str, str]] = {}
    try:
        data = llm.chat_json(CLASSIFY_SYSTEM, user)
        rows = data.get("results", []) if isinstance(data, dict) else data
        for row in rows:
            cat = str(row.get("category", "")).lower().strip()
            if cat in VALID_CATEGORIES:
                out[int(row["id"])] = (cat, "llm")
    except Exception as e:
        logger.warning(f"Classification call failed, using rule-based fallback: {e}")

    for i, text in batch:  # anything missing or invalid -> rules
        if i not in out:
            out[i] = (rule_based_category(text), "rule")
    return out


def classify_document(comments: List[Dict], llm: LLMClient, cfg: Config) -> None:
    """Fills comment['category'] and comment['method'] in place."""
    # Stage 1: repeats across the whole document (first occurrence is kept as the original)
    seen: List[str] = []
    pending: List[int] = []
    for idx, c in enumerate(comments):
        norm = c["text"].lower().strip()
        if seen and process.extractOne(
            norm, seen, scorer=fuzz.ratio, score_cutoff=cfg.similarity_threshold
        ):
            c["category"], c["method"] = "repeated", "similarity"
        else:
            seen.append(norm)
            pending.append(idx)

    # Stage 2: optional LLM, page by page, chunked
    if not cfg.classification_llm_enabled or llm is None:
        for i in pending:
            comments[i]["category"] = rule_based_category(comments[i]["text"])
            comments[i]["method"] = "rule"
        return

    by_page: Dict[int, List[int]] = {}
    for idx in pending:
        by_page.setdefault(comments[idx]["page"], []).append(idx)

    batches: List[List[Tuple[int, str]]] = []
    for page_no in sorted(by_page):
        idxs = by_page[page_no]
        for k in range(0, len(idxs), cfg.llm_batch_size):
            batches.append([(i, comments[i]["text"]) for i in idxs[k:k + cfg.llm_batch_size]])

    with ThreadPoolExecutor(max_workers=cfg.llm_max_workers) as ex:
        for result in ex.map(lambda b: classify_batch(llm, b), batches):
            for i, (cat, method) in result.items():
                comments[i]["category"], comments[i]["method"] = cat, method


# ============================
# SCREENSHOT + UID
# ============================

def capture_screenshot(page: fitz.Page, c: Dict, uid: str, img_dir: Path, cfg: Config) -> str:
    """Crop around the comment box and its arrow target; grow to min size; stay inside the page."""
    box = fitz.Rect(c["rect"])
    for p in c["arrow_pts"]:
        box.include_point(p)

    cx, cy = (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2
    w = max(box.width * cfg.screenshot_margin, cfg.screenshot_min_width)
    h = max(box.height * cfg.screenshot_margin, cfg.screenshot_min_height)
    crop = fitz.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    pr = page.rect  # shift the crop back inside the page rather than shrinking it
    if crop.x0 < pr.x0:
        crop.x1 += pr.x0 - crop.x0
        crop.x0 = pr.x0
    if crop.x1 > pr.x1:
        crop.x0 -= crop.x1 - pr.x1
        crop.x1 = pr.x1
    if crop.y0 < pr.y0:
        crop.y1 += pr.y0 - crop.y0
        crop.y0 = pr.y0
    if crop.y1 > pr.y1:
        crop.y0 -= crop.y1 - pr.y1
        crop.y1 = pr.y1
    crop = crop & pr

    zoom = cfg.screenshot_dpi / 72.0
    pix = page.get_pixmap(clip=crop, matrix=fitz.Matrix(zoom, zoom), annots=True)
    out = img_dir / f"{uid}.png"
    pix.save(str(out))
    return str(out).replace("\\", "/")


ENRICH_SYSTEM = "You inspect cropped snippets of engineering drawings. Reply with JSON only."


def enrich_snapshot(llm: LLMClient, shot_path: Path, comment_text: str, annot_type: str) -> Optional[Dict]:
    """
    From the teammate's inspect_snapshot_vision, narrowed to what a crop can actually tell us:
      is_handwritten  - Y/N, a markup property the PDF annotation does not carry
      visual_feature  - what is being marked (pump P-101, nozzle N3, pipe line ...): the seed
                        for the entity graph (entities / comment_entity_edges)
    Deliberately NOT taken from the model: category (the classifier owns it) and any
    'confidence' number (a self-reported score is not a measured accuracy).
    """
    try:
        png = Path(shot_path).read_bytes()
    except OSError:
        return None
    user = (
        "This is a cropped snippet from an engineering drawing around one review annotation.\n"
        f"Annotation type: {annot_type}\nAnnotation text: {comment_text!r}\n\n"
        "Return JSON with exactly these keys:\n"
        '  "is_handwritten": "Y" if any handwritten note or hand-drawn mark is visible, else "N"\n'
        '  "visual_feature": short name of the equipment, line or area the annotation points at, '
        'copying any visible tag (e.g. "pump P-101", "nozzle N3", "line 4in-CS-102"); null if unclear\n'
        "Do not guess tags that are not visible."
    )
    try:
        data = llm.chat_vision_json(ENRICH_SYSTEM, user, png)
    except Exception as e:
        logger.warning(f"Snapshot enrichment failed for {shot_path}: {e}")
        return None
    if not isinstance(data, dict):
        return None
    hw = str(data.get("is_handwritten") or "").strip().upper()
    vf = data.get("visual_feature")
    vf = str(vf).strip() if vf not in (None, "", "null") else ""
    return {"is_handwritten": "Y" if hw == "Y" else "N", "visual_feature": vf[:255]}


UID_MAX_LEN = 100   # PRAJ comments.comment_id is VARCHAR(100); candidate schema allows 128
UID_HASH_HEX = 12   # 48 bits of the source file's SHA-256


def make_uid(meta: Dict, page_no: int, y_pos: float, page_height: float, seq: int, cfg: Config,
             file_hash: str = "") -> str:
    """
    PROJECT-DRAWING-REV-page-row-seq-HHHHHHHHHHHH
      REV       revision (or NA): when both revisions are resolved and differ (RA vs RB),
                this segment alone keeps their ids apart
      HHHH...   first UID_HASH_HEX (12) hex of the source file's SHA-256, upper-case (the full
                digest is written to the source_file_sha256 column). It is derived from the
                source PDF BYTES and distinguishes source files probabilistically: two
                different files get different suffixes with high probability, not with
                certainty. With 12 hex (48 bits) the chance of any collision among files that
                share every other id segment is about 2e-9 for 1,000 such files and 2e-7 for
                10,000.
    Length: at most UID_MAX_LEN (100). The hash suffix is never truncated; if the id would
    be too long, PROJECT / DRAWING / REV are shortened (longest first, each kept >= 1 char),
    so the segment structure is unchanged. Prefix shortening only happens for extreme
    metadata or page/seq numbers; with the normal caps (20/40/8) and 3-digit page/row/seq
    the id is at most 95 characters and nothing is shortened.
    What the id does NOT tell you:
      * Byte-identical files have the same source_file_sha256 and the same hash suffix, but
        their full ids can still differ: PROJECT/DRAWING/REV come from the filename, so a
        renamed copy (e.g. 'copy_of_drawing.pdf') gets a different prefix.
      * Different full ids therefore do not, by themselves, prove two PDFs are different
        documents. Detect duplicates and reprocessing by comparing source_file_sha256,
        never by comparing comment_id.
    The first two segments stay PROJECT and DRAWING (no dashes inside), so existing
    consumers that split on '-' (ingest.parse_uid) keep working.
    """
    row = min(cfg.row_density - 1, max(0, int((y_pos / page_height) * cfg.row_density)))
    project = re.sub(r"[^A-Z0-9]", "", str(meta.get("project") or "DOC").upper())[:20] or "DOC"
    drawing = re.sub(r"[^A-Z0-9]", "", str(meta.get("drawing_number") or "DWG").upper())[:40] or "DWG"
    rev = re.sub(r"[^A-Z0-9]", "", str(meta.get("praj_revision") or "NA").upper())[:8] or "NA"
    suffix = ""
    if file_hash:
        if len(file_hash) < UID_HASH_HEX or not re.fullmatch(r"[0-9a-fA-F]+", file_hash):
            raise ValueError(f"file_hash must be >= {UID_HASH_HEX} hex characters")
        suffix = f"-{file_hash[:UID_HASH_HEX].upper()}"
    tail = f"-{page_no:03d}-{row:03d}-{seq:03d}{suffix}"
    segs = [project, drawing, rev]
    budget = UID_MAX_LEN - len(tail) - 2          # two dashes between the three prefix segments
    if budget < 3:
        raise ValueError(f"comment id tail too long to fit {UID_MAX_LEN} characters: {tail!r}")
    while sum(map(len, segs)) > budget:           # shorten the prefix, never the hash suffix
        i = max(range(3), key=lambda k: (len(segs[k]), -k))
        segs[i] = segs[i][:-1]
    return f"{segs[0]}-{segs[1]}-{segs[2]}{tail}"


def make_position_key(page_no: int, rect: fitz.Rect, page_rect: fitz.Rect, cfg: Config) -> str:
    """
    Revision-independent location of a comment: page + grid cell of the box centre.
    NOT unique (two comments can share a cell) and NOT an id: it is a matching hint for the
    revision diff, to be combined with text similarity there.
    """
    cx = (rect.x0 + rect.x1) / 2 - page_rect.x0
    cy = (rect.y0 + rect.y1) / 2 - page_rect.y0
    n = cfg.row_density
    col = min(n - 1, max(0, int(cx / max(page_rect.width, 1e-6) * n)))
    row = min(n - 1, max(0, int(cy / max(page_rect.height, 1e-6) * n)))
    return f"P{page_no:03d}-R{row:03d}-C{col:03d}"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ============================
# DOCUMENT PIPELINE
# ============================

COLUMNS = [
    "sr_no", "praj_document_number", "praj_revision_number", "customer_document_number",
    "customer_revision", "page_sheet", "comment_id", "actual_extracted_comment",
    "snapshot_file", "name_of_person_commented", "email_of_person_commented",
    "date_of_comment", "time_of_comment", "comment_color", "is_client_comment",
    "comment_category", "is_handwritten", "extraction_confidence_percent",
    "annotation_type", "classification_method", "comment_source",
    "visual_feature",
    # identity / provenance (appended so column order of existing fields is unchanged)
    "position_key", "drawing_number_source", "revision_source", "source_file_sha256",
]

# Extraction path -> the old fixed score. Native and hosted-vision values are kept as they
# were so existing outputs stay comparable; they are path labels, NOT measured accuracy.
# OCR paths get no number at all until Phase 2 measures them.
_PATH_SCORE = {"native": 100, "vision": 85}


def process_pdf(pdf_path: Path, cfg: Config, llm: Optional[LLMClient], vision_allowed: bool,
                ocr=None, max_pages: Optional[int] = None) -> Tuple[int, pd.DataFrame]:
    job_dir = Path("output") / pdf_path.stem
    img_dir = job_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    review_dir = job_dir / "review_candidates"
    review_dir.mkdir(parents=True, exist_ok=True)

    source_hash = file_sha256(pdf_path)
    doc = fitz.open(str(pdf_path))
    try:
        meta = extract_metadata(doc, pdf_path.name, llm, cfg)
        logger.info(f"{pdf_path.name} | metadata: {meta}")

        # ---- collect comments page by page (native, then vision fallback per empty page) ----
        comments: List[Dict] = []
        empty_pages = 0
        extraction_error_pages = 0
        recovered: Dict[str, int] = {}
        review_candidates: List[Dict] = []
        n_pages = min(len(doc), max_pages) if max_pages else len(doc)
        for pno in range(n_pages):
            page = doc[pno]
            found, native_ok = collect_comments(doc, page, pno + 1)
            if not native_ok:
                extraction_error_pages += 1
                logger.warning(
                    f"{pdf_path.name} page {pno + 1}: native annotation extraction failed; "
                    f"fallback will be attempted only as an explicit recovery path."
                )
            elif not found:
                empty_pages += 1
            if not native_ok or not found:
                found, reviews, path = fallback_page(page, pno + 1, llm, cfg, review_dir,
                                                     vision_allowed, ocr)
                review_candidates.extend(reviews)
                if found:
                    recovered[path] = recovered.get(path, 0) + 1
            comments.extend(found)
        logger.info(
            f"{pdf_path.name} | {n_pages}/{len(doc)} pages | {len(comments)} comments | "
            f"{empty_pages} pages with no native annotations | "
            f"{extraction_error_pages} native extraction-error pages | "
            f"pages recovered by fallback: {recovered or 'none'}"
        )

        # ---- classify ----
        if comments:
            classify_document(comments, llm, cfg)

        # ---- screenshots + records ----
        records: List[Dict] = []
        enriched = 0
        page_sequences: Dict[int, int] = {}
        for n, c in enumerate(tqdm(comments, desc=pdf_path.stem, leave=False), start=1):
            page_no = c["page"]
            page_sequences[page_no] = page_sequences.get(page_no, 0) + 1
            page_seq = page_sequences[page_no]
            page = doc[page_no - 1]
            uid = make_uid(
                meta, page_no, c["rect"].y0, page.rect.height,
                page_seq, cfg, source_hash
            )
            shot = capture_screenshot(page, c, uid, img_dir, cfg)
            is_client = "N" if c["author"].lower() in ("praj", "internal", "unknown", "") else "Y"
            is_handwritten, visual_feature = "N", ""
            if (cfg.enrichment_enabled and llm is not None
                    and enriched < cfg.enrichment_max_comments and c["source"] != "ocr_page"):
                enriched += 1
                e = enrich_snapshot(llm, Path(shot), c["text"], c["annot_type"])
                if e:
                    is_handwritten, visual_feature = e["is_handwritten"], e["visual_feature"]
            records.append({
                "sr_no": n,
                "praj_document_number": meta["drawing_number"],
                "praj_revision_number": meta["praj_revision"],
                "customer_document_number": meta["customer_doc"],
                "customer_revision": meta["customer_revision"],
                "page_sheet": c["page"],
                "comment_id": uid,
                "actual_extracted_comment": c["text"],
                "snapshot_file": shot,
                "name_of_person_commented": c["author"],
                "email_of_person_commented": c.get("email", ""),
                "date_of_comment": c["date"],
                "time_of_comment": c["time"],
                "comment_color": c["color"],
                "is_client_comment": is_client,
                "comment_category": c["category"],
                "is_handwritten": is_handwritten,
                "extraction_confidence_percent": _PATH_SCORE.get(c["source"]),
                "annotation_type": c["annot_type"],
                "classification_method": c["method"],
                "comment_source": c["source"],
                "visual_feature": visual_feature,
                "position_key": make_position_key(c["page"], c["rect"], page.rect, cfg),
                "drawing_number_source": meta["drawing_number_source"],
                "revision_source": meta["revision_source"],
                "source_file_sha256": source_hash,
            })
    finally:
        doc.close()

    # ---- per-PDF outputs ----
    with open(job_dir / "comments.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=4, ensure_ascii=False)

    df = pd.DataFrame(records, columns=COLUMNS)
    df.to_csv(job_dir / "final_output.csv", index=False)
    with open(job_dir / "review_candidates.json", "w", encoding="utf-8") as f:
        json.dump(review_candidates, f, indent=2, ensure_ascii=False)
    pd.DataFrame(review_candidates).to_csv(job_dir / "review_candidates.csv", index=False)

    total = len(df)
    rows = []
    if total:
        for cat, grp in df.groupby("comment_category"):
            rows.append({"Category": cat, "Count": len(grp),
                         "Percentage": f"{round(len(grp) / total * 100, 1)}%"})
    rows.append({"Category": "TOTAL", "Count": total, "Percentage": "100%" if total else "0%"})
    pd.DataFrame(rows).to_csv(job_dir / "summary.csv", index=False)

    logger.info(f"Done: {pdf_path.stem} | {total} comments | {job_dir}")
    return total, df


def write_master_outputs(all_dfs: Dict[str, pd.DataFrame]) -> None:
    """Combine every processed PDF's records into one master comments file + one summary."""
    out_dir = Path("output")
    frames = []
    for name, df in all_dfs.items():
        if df.empty:
            continue
        tagged = df.copy()
        tagged.insert(0, "source_file", name)
        frames.append(tagged)

    if not frames:
        logger.warning("No comments extracted across any PDF; skipping master outputs")
        return

    master = pd.concat(frames, ignore_index=True)
    master.to_csv(out_dir / "master_comments.csv", index=False)
    master.to_json(out_dir / "master_comments.json", orient="records", indent=2, force_ascii=False)

    # per-file totals
    per_file = master.groupby("source_file").size().reset_index(name="comment_count")
    # category breakdown, overall
    by_category = master.groupby("comment_category").size().reset_index(name="count")
    # extraction-source breakdown, overall (native vs vision)
    by_source = master.groupby("comment_source").size().reset_index(name="count")

    with pd.ExcelWriter(out_dir / "master_summary.xlsx") as xw:
        per_file.to_excel(xw, sheet_name="per_file", index=False)
        by_category.to_excel(xw, sheet_name="by_category", index=False)
        by_source.to_excel(xw, sheet_name="by_extraction_source", index=False)

    per_file.to_csv(out_dir / "master_summary_per_file.csv", index=False)
    by_category.to_csv(out_dir / "master_summary_by_category.csv", index=False)
    by_source.to_csv(out_dir / "master_summary_by_source.csv", index=False)

    logger.info(
        f"Master outputs written: {len(master)} total comments across {len(frames)} file(s) "
        f"-> output/master_comments.csv, master_summary_*.csv, master_summary.xlsx"
    )


# ============================
# MAIN
# ============================

def dry_run_report(pdfs: List[Path], cfg: Config) -> None:
    """
    No LLM calls at all. For every PDF/page reports:
      - native annotations found (the free, exact path)
      - pages where native annotation iteration failed (NOT equivalent to zero annotations)
      - color-boxes detected on empty/error pages (what the vision fallback would attempt)
    Use this before a real run to see which files will actually benefit from the
    vision fallback vs which need different box colors / a different approach entirely.
    """
    print(f"\n{'File':45s} {'Pages':>6s} {'NativeAnnots':>13s} {'EmptyPages':>11s} {'ExtractErrors':>13s} {'ColorBoxesFound':>16s}")
    print("-" * 112)
    for pdf_path in pdfs:
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            print(f"{pdf_path.name:45s}  FAILED TO OPEN: {e}")
            continue
        native_total = 0
        empty_pages = 0
        extraction_errors = 0
        color_box_total = 0
        color_counts: Dict[str, int] = {}
        n_pages = len(doc)
        for page in doc:
            try:
                found, native_ok = collect_comments(doc, page, 0)
                if not native_ok:
                    extraction_errors += 1
                    boxes = detect_color_boxes(page, cfg)
                    color_box_total += len(boxes)
                    for b in boxes:
                        color_counts[b["color"]] = color_counts.get(b["color"], 0) + 1
                elif found:
                    native_total += len(found)
                else:
                    empty_pages += 1
                    boxes = detect_color_boxes(page, cfg)
                    color_box_total += len(boxes)
                    for b in boxes:
                        color_counts[b["color"]] = color_counts.get(b["color"], 0) + 1
            except Exception as e:
                logger.warning(f"Skipping a page in {pdf_path.name} after an error: {e}")
        doc.close()
        detail = f" ({', '.join(f'{k}:{v}' for k, v in color_counts.items())})" if color_counts else ""
        print(f"{pdf_path.name:45s} {n_pages:6d} {native_total:13d} "
              f"{empty_pages:11d} {extraction_errors:13d} {color_box_total:16d}{detail}")
    print("-" * 95)
    if cfg.vision_mode == "palette":
        print(
            "Mode: palette. Read this as: NativeAnnots>0 -> free/exact extraction already works.\n"
            "EmptyPages>0 & ColorBoxesFound==0 -> this file's comment boxes (if any) are NOT one of\n"
            "  your configured vision.colors, or there are no boxes at all (true scan/handwriting) --\n"
            "  run probe_colors.py on it, add the RGB you find to vision.colors, or it needs a\n"
            "  different approach (full-page OCR) rather than box detection.\n"
            "EmptyPages>0 & ColorBoxesFound>0 -> vision fallback should extract these once your\n"
            "  LLM key has credit -- worth rerunning just this file after fixing that.\n"
        )
    else:
        print(
            "Mode: generic (hue-clustered). Read this as: NativeAnnots>0 -> free/exact extraction\n"
            "  already works, no LLM needed.\n"
            "EmptyPages>0 & ColorBoxesFound==0 -> no sufficiently large/solid/colorful region was\n"
            "  found at all -- likely a true scan, handwriting, or line-art markup with no filled\n"
            "  box (a different problem: full-page OCR, not box detection). Run probe_colors.py on\n"
            "  it to see what colors (if any) are actually present, and tune min_spread/min_value/\n"
            "  box_min_width_pt/box_min_height_pt in config.yaml if a real box is being filtered out.\n"
            "EmptyPages>0 & ColorBoxesFound>0 -> vision fallback should extract these once your\n"
            "  LLM key has credit -- worth rerunning just this file after fixing that.\n"
        )



def select_vision_pdfs(pdfs: List[Path], cfg: Config) -> set:
    """Choose up to cfg.vision_max_pdfs that actually contain locally detected visual candidates."""
    selected = set()
    if not cfg.vision_enabled or cfg.vision_max_pdfs <= 0:
        return selected
    for pdf_path in pdfs:
        if len(selected) >= cfg.vision_max_pdfs:
            break
        try:
            doc = fitz.open(str(pdf_path))
            has_candidate = False
            for page in doc:
                found, native_ok = collect_comments(doc, page, 0)
                if native_ok and found:
                    continue
                if detect_color_boxes(page, cfg):
                    has_candidate = True
                    break
            doc.close()
            if has_candidate:
                selected.add(pdf_path.resolve())
                logger.info(f"Vision selected {len(selected)}/{cfg.vision_max_pdfs}: {pdf_path.name}")
        except Exception as e:
            logger.warning(f"Vision pre-scan failed for {pdf_path.name}: {e}")
    return selected


def collect_pdfs(input_arg: str) -> List[Path]:
    p = Path(input_arg)
    if p.is_file() and p.suffix.lower() == ".pdf":
        return [p]
    if p.is_dir():
        return sorted(p.glob("**/*.pdf"))
    from glob import glob
    return [Path(x) for x in sorted(glob(input_arg))]


def main():
    ap = argparse.ArgumentParser(description="Engineering drawing comment extraction")
    ap.add_argument("--input", default="input", help="PDF file, folder, or glob pattern (default: 'input')")
    ap.add_argument("--config", default=str(Path(__file__).resolve().parent / "config.yaml"))
    ap.add_argument("--dry-run", action="store_true",
                    help="Check native annotations + color-box detection for every PDF, no LLM calls, no output files.")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="Process only the first N pages of each PDF (smoke test).")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    cfg = Config.from_yaml(cfg_path)

    pdfs = collect_pdfs(args.input)
    if not pdfs:
        logger.warning(f"No PDFs found at: {args.input}")
        return

    if args.dry_run:
        dry_run_report(pdfs, cfg)
        return

    # Only demand an API key when an enabled feature actually calls the hosted LLM:
    # an all-local run (native + local OCR boxes, rules) needs no key and sends nothing out.
    llm = LLMClient(cfg) if cfg.llm_needed() else None
    if llm is None:
        logger.info("No hosted-LLM feature enabled: running fully local, no API key needed")

    ocr = None
    if cfg.ocr_enabled:
        from local_ocr import LocalOCR, ocr_available
        ok, why = ocr_available()
        if ok:
            ocr = LocalOCR(cfg.ocr_model, cfg.ocr_dpi, cfg.ocr_max_new_tokens,
                           cfg.ocr_api_key_env, cfg.ocr_device)  # weights load on first use
        else:
            logger.warning(f"ocr.enabled is true but the OCR stack is unavailable ({why}); "
                           f"install requirements-ocr.txt. Continuing without local OCR.")

    if cfg.vision_enabled and cfg.vision_box_reader == "llm" and llm is not None:
        vision_selected = select_vision_pdfs(pdfs, cfg)
    else:
        vision_selected = set()
    logger.info(f"Found {len(pdfs)} PDF(s); processing one at a time")
    logger.info(f"Box reader: {cfg.vision_box_reader if cfg.vision_enabled else 'off'} | "
                f"hosted vision budget used by {len(vision_selected)} PDF(s) | "
                f"local OCR: {'on' if ocr else 'off'} (full page: {cfg.ocr_full_page and bool(ocr)})")

    start = time.time()
    results: Dict[str, int] = {}
    all_dfs: Dict[str, pd.DataFrame] = {}
    for pdf in pdfs:  # one document per iteration
        try:
            count, df = process_pdf(pdf, cfg, llm, pdf.resolve() in vision_selected,
                                    ocr=ocr, max_pages=args.max_pages)
            results[pdf.name] = count
            all_dfs[pdf.name] = df
        except Exception as e:
            logger.error(f"Failed on {pdf.name}: {e}", exc_info=True)
            results[pdf.name] = 0
            all_dfs[pdf.name] = pd.DataFrame(columns=COLUMNS)

    write_master_outputs(all_dfs)

    logger.info("=" * 50)
    logger.info(f"Completed in {round(time.time() - start, 1)}s | comments: {sum(results.values())}")
    for name, count in results.items():
        logger.info(f"  {name}: {count}")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
"""
local_ocr.py -- on-prem OCR fallback using LightOnOCR-2-1B (Hugging Face transformers).

Adapted from the teammate's Colab notebook (OCREngine). Differences:
  * torch / transformers / PIL are imported lazily, so the main pipeline runs on a
    machine without them (Windows laptop, no GPU) as long as ocr.enabled is false.
  * Two entry points: ocr_rect() reads one detected comment box (localised, preferred),
    ocr_page_lines() reads a whole page (last resort, needs filtering afterwards).
  * The model never leaves the machine, so this is the confidentiality-safe reader.

Weights are roughly 2 GB in bf16 and download on first use. Run it on Colab / a GPU box,
not over a metered connection.
"""
from __future__ import annotations

import io
import logging
import os
import re
import tempfile
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger("comment_extractor.ocr")

_NOISE_LINES = {"---", "***", "___", "--", "-", "```", "```plaintext", "plaintext"}


def clean_ocr_text(raw: str) -> List[str]:
    """Strip the HTML/markdown scaffolding LightOnOCR emits and return non-trivial lines."""
    text = re.sub(r"<[^>]*>", "", raw or "", flags=re.DOTALL)
    out: List[str] = []
    for line in text.splitlines():
        clean = re.sub(r"^#+\s*", "", line).strip()
        if clean in _NOISE_LINES:
            continue
        if clean.startswith("```") or clean.startswith("<") or "style=" in clean \
                or "border:" in clean or "display:" in clean or "justify-content:" in clean:
            continue
        if len(clean) >= 3:
            out.append(clean)
    return out


def ocr_available() -> Tuple[bool, str]:
    """Cheap check (no weight download) that the OCR stack can be imported."""
    try:
        import torch  # noqa: F401
        from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception as e:  # ImportError, or an old transformers without the classes
        return False, f"{type(e).__name__}: {e}"
    return True, "ok"


class LocalOCR:
    """Lazy-loading LightOnOCR engine. Construct freely; weights load on the first read."""

    def __init__(self, model_name: str = "lightonai/LightOnOCR-2-1B", dpi: int = 150,
                 max_new_tokens: int = 2048, token_env: str = "HF_TOKEN", device: str = "auto"):
        self.model_name = model_name
        self.dpi = dpi
        self.max_new_tokens = max_new_tokens
        self.token_env = token_env
        self.device_pref = device
        self.model = None
        self.processor = None
        self.device = None
        self.dtype = None

    # ---- model loading ----------------------------------------------------
    def _load(self) -> None:
        if self.model is not None:
            return
        import torch
        from transformers import LightOnOcrForConditionalGeneration, LightOnOcrProcessor

        if self.device_pref == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = self.device_pref
        if self.device == "cuda":
            self.dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        else:
            self.dtype = torch.float32
            logger.warning("Local OCR is running on CPU: expect minutes per page.")

        token = os.getenv(self.token_env) or None
        logger.info(f"Loading {self.model_name} on {self.device} ({self.dtype}) ...")
        try:
            model = LightOnOcrForConditionalGeneration.from_pretrained(
                self.model_name, dtype=self.dtype, token=token)
        except TypeError:  # older transformers use torch_dtype
            model = LightOnOcrForConditionalGeneration.from_pretrained(
                self.model_name, torch_dtype=self.dtype, token=token)
        self.model = model.to(self.device).eval()
        self.processor = LightOnOcrProcessor.from_pretrained(self.model_name, token=token)
        logger.info("Local OCR model ready.")

    # ---- inference --------------------------------------------------------
    def _run_png(self, png_bytes: bytes) -> str:
        import torch
        from PIL import Image

        self._load()
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        img.save(tmp.name)
        try:
            messages = [{"role": "user", "content": [{"type": "image", "url": tmp.name}]}]
            inputs = self.processor.apply_chat_template(
                messages, add_generation_prompt=True, tokenize=True,
                return_dict=True, return_tensors="pt")
            inputs = {
                k: (v.to(self.device, dtype=self.dtype) if v.is_floating_point() else v.to(self.device))
                for k, v in inputs.items()
            }
            with torch.inference_mode():
                out_ids = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens)
            gen = out_ids[0, inputs["input_ids"].shape[1]:]
            return self.processor.decode(gen, skip_special_tokens=True)
        finally:
            os.unlink(tmp.name)
            if self.device == "cuda":
                torch.cuda.empty_cache()

    def ocr_rect(self, page: fitz.Page, rect: fitz.Rect, pad: float = 8) -> List[str]:
        """OCR one region of a page (a detected comment box). Returns cleaned lines."""
        crop = fitz.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad) & page.rect
        zoom = self.dpi / 72.0
        pix = page.get_pixmap(clip=crop, matrix=fitz.Matrix(zoom, zoom), annots=True, alpha=False)
        return clean_ocr_text(self._run_png(pix.tobytes("png")))

    def ocr_page_lines(self, page: fitz.Page) -> List[str]:
        """OCR a whole page. Returns cleaned lines (drawing text included: filter afterwards)."""
        zoom = self.dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), annots=True, alpha=False)
        return clean_ocr_text(self._run_png(pix.tobytes("png")))


# ---- turning OCR'd box text into comment fields -----------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_DATE = re.compile(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\b")
_TIME = re.compile(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b")


def parse_box_lines(lines: List[str]) -> Optional[dict]:
    """
    Split an OCR'd comment box into header fields and body. Deterministic: email/date/time
    by regex; a header line is one that is mostly those tokens. Author is left 'Unknown'
    unless a header line holds a name next to the email (common markup layout).
    Returns None when no body text is left.
    """
    email = date = time_val = None
    author = "Unknown"
    body: List[str] = []
    for line in lines:
        e, d, t = _EMAIL.search(line), _DATE.search(line), _TIME.search(line)
        email = email or (e.group(0) if e else None)
        date = date or (d.group(1) if d else None)
        time_val = time_val or (t.group(1) if t else None)
        residue = line
        for m in (e, d, t):
            if m:
                residue = residue.replace(m.group(0), " ")
        residue = re.sub(r"[\s|,;:()\-]+", " ", residue).strip()
        is_header = bool(e or d or t) and len(residue) <= max(3, len(line) // 3) + 25
        if is_header:
            if e and residue and author == "Unknown" and len(residue.split()) <= 4:
                author = residue
            continue
        body.append(line)
    text = re.sub(r"\s+", " ", " ".join(body)).strip()
    if len(text) < 3:
        return None
    return {"author": author, "email": email or "", "date": date or "NA",
            "time": time_val or "NA", "text": text}

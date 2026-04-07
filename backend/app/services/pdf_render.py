"""
PDF page utilities built on PyMuPDF (`fitz`) — pure-Python-wheel, no system
Poppler/Ghostscript dependency, which keeps the single-GPU-box install
simple.

Used by the ingestion pipeline to (a) count pages at upload time and (b)
rasterize each page to an image for the VLM OCR call (PRD 2.A #1).
"""

from __future__ import annotations

import base64
from pathlib import Path

import fitz  # PyMuPDF

# 200 DPI is a reasonable default for VLM OCR of dense scientific text —
# high enough to keep small font/subscript/superscript legible without
# producing enormous images. Tune in AGENT_TASKS if the real olmOCR model
# has a documented preferred resolution.
_RENDER_DPI = 200


def get_page_count(pdf_path: Path | str) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def render_page_to_png_base64(pdf_path: Path | str, page_number: int) -> str:
    """`page_number` is 1-indexed to match the rest of the app."""
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_number - 1)
        pixmap = page.get_pixmap(dpi=_RENDER_DPI)
        png_bytes = pixmap.tobytes("png")
    return base64.b64encode(png_bytes).decode("ascii")

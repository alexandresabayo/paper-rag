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


class PDFValidationError(ValueError):
    """Base for all upload-time PDF validation failures (ISSUE-010,
    AGENT_TASKS.md). Callers (the ingestion router) catch this base class
    to turn any of them into a 4xx, and the specific subclasses when they
    need a distinct message per case."""


class PDFCorruptedError(PDFValidationError):
    """The bytes don't parse as a PDF at all - e.g. a renamed non-PDF
    file, a truncated download, or genuinely corrupted content. Verified
    against real PyMuPDF behavior: opening garbage bytes raises
    `fitz.FileDataError` (a `RuntimeError` subclass), but other malformed
    inputs can surface as other exceptions from the same `fitz.open()`
    call, so this wraps any of them uniformly rather than pattern-
    matching on one specific exception type."""


class PDFEncryptedError(PDFValidationError):
    """The PDF opens, but requires a password. Verified against real
    PyMuPDF behavior: an encrypted PDF opens fine and even reports a
    (misleadingly normal-looking) `page_count` without raising - the
    actual signal is `doc.needs_pass`, checked explicitly before trusting
    anything else about the document. (`load_page()` is what eventually
    raises on an encrypted doc, but only if something tries to read a
    page - checking `needs_pass` upfront means we never get that far.)"""


class PDFEmptyError(PDFValidationError):
    """The PDF is valid and unencrypted, but has zero pages. Real,
    reachable case: pypdf's own `PdfWriter` can produce a structurally
    valid zero-page PDF that PyMuPDF opens without complaint
    (`page_count == 0`, `needs_pass == 0`) - not just a theoretical
    edge case (see tests/test_pdf_validation.py)."""


def inspect_pdf_bytes(file_bytes: bytes) -> int:
    """Validate `file_bytes` as an ingestible PDF *before* anything is
    written to disk or any DB row is created (ISSUE-010) - the router
    calls this first, so a rejected upload never touches storage. Returns
    the page count on success (the router reuses it directly rather than
    re-opening the file a second time via `get_page_count`).

    Raises `PDFCorruptedError` / `PDFEncryptedError` / `PDFEmptyError` as
    appropriate; see each class's docstring for how it was verified
    against real PyMuPDF behavior, not assumed.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any parse failure is "corrupted" from the caller's perspective
        raise PDFCorruptedError(f"could not be parsed as a PDF: {exc}") from exc

    try:
        if doc.needs_pass:
            raise PDFEncryptedError("PDF is password-protected; encrypted PDFs are not supported")
        page_count = doc.page_count
        if page_count == 0:
            raise PDFEmptyError("PDF has zero pages")
        return page_count
    finally:
        doc.close()


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

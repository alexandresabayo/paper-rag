"""
Page extraction providers — PRD 2.A #1 and the "Extraction strategy" note
at the top of PRD Section 2.A.

The pipeline (app/pipeline/tasks.py) always tries the **primary** provider
first (`get_primary_ocr_provider()`) and only falls back to
`PyPDFFallbackProvider` if the primary raises `OCRExtractionError` — that
try/primary-then-fallback decision lives in the pipeline, not here, since
"worst case fallback" is a pipeline-level policy, not a provider's own
choice.

MOCK_MODE swaps the primary provider for `DevShimVLMProvider`, which is
explicitly a development convenience, not a second real implementation —
see its docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pypdf import PdfReader

from app.config import settings
from app.providers.ollama_client import OllamaClient, OllamaError
from app.services import json_repair
from app.services.prompt_loader import get_prompt


class OCRExtractionError(RuntimeError):
    """Raised by the primary provider when it fails outright for a page —
    signals the pipeline to fall back to PyPDFFallbackProvider."""


@dataclass(frozen=True)
class PageExtractionResult:
    text: str


class OCRProvider(Protocol):
    def extract_page(self, pdf_path: Path, page_number: int) -> PageExtractionResult: ...


class OlmOCRVisionProvider:
    """Primary path: a vision-language model called through Ollama with the
    custom transcription prompt (prompts/ingestion/ocr_transcribe.md),
    overriding olmOCR's own stock prompting per PRD 2.A #1.

    Real implementation — not exercised against a live Ollama server in
    this environment (see AGENT_TASKS.md). Swap in once Ollama is running
    with an OCR-capable vision model pulled under `settings.OCR_MODEL`.
    """

    def __init__(self, client: OllamaClient | None = None):
        self._client = client or OllamaClient()

    def extract_page(self, pdf_path: Path, page_number: int) -> PageExtractionResult:
        from app.services.pdf_render import render_page_to_png_base64

        image_b64 = render_page_to_png_base64(pdf_path, page_number)
        prompt_spec = get_prompt("ingestion/ocr_transcribe")

        try:
            raw = self._client.generate(
                model=prompt_spec.model,
                prompt=prompt_spec.render(),
                images_base64=[image_b64],
                json_schema=prompt_spec.schema,
                temperature=prompt_spec.temperature,
            )
            parsed = json_repair.repair_json(raw)
            text = parsed["text"]
        except (OllamaError, json_repair.JSONRepairError, KeyError) as exc:
            raise OCRExtractionError(f"VLM OCR failed on page {page_number}: {exc}") from exc

        if not text or not text.strip():
            raise OCRExtractionError(f"VLM OCR returned empty text on page {page_number}")

        return PageExtractionResult(text=text)


class PyPDFFallbackProvider:
    """Worst-case fallback (PRD 2.A #1, Section 3 "Corrupted PDF Text
    Extraction"): standard, non-AI text extraction. Only ever produces raw
    text — the pipeline must not call summary/keyword generation on its
    output (metadata/summary/keywords stay N/A, per Section 2.A's
    extraction-strategy note)."""

    def extract_page(self, pdf_path: Path, page_number: int) -> PageExtractionResult:
        reader = PdfReader(str(pdf_path))
        page = reader.pages[page_number - 1]
        text = page.extract_text() or ""
        return PageExtractionResult(text=text)


class DevShimVLMProvider:
    """DEV-ONLY. Not a second real OCR implementation.

    There is no GPU / running Ollama / olmOCR weights available in this
    build environment, so this shim substitutes `PyPDFFallbackProvider`'s
    text while presenting it to the pipeline as if the primary VLM path
    had succeeded. That's what lets the *rest* of the pipeline
    (per-page summary/keyword calls, incremental doc-summary folding,
    embeddings, checkpointing/retry, retrieval, scenario classification)
    run and be tested end-to-end without a GPU.

    This means MOCK_MODE demos will not exhibit the real "fallback ⇒ N/A
    enrichment" behavior for OCR-recoverable pages, because every page
    looks like a VLM success. Do not mistake this for validation of the
    real OCR path — see AGENT_TASKS.md "Wire up real model providers".
    """

    def __init__(self) -> None:
        self._fallback = PyPDFFallbackProvider()

    def extract_page(self, pdf_path: Path, page_number: int) -> PageExtractionResult:
        return self._fallback.extract_page(pdf_path, page_number)


def get_primary_ocr_provider() -> OCRProvider:
    if settings.MOCK_MODE:
        return DevShimVLMProvider()
    return OlmOCRVisionProvider()


def get_fallback_ocr_provider() -> OCRProvider:
    return PyPDFFallbackProvider()

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

import openai
from pypdf import PdfReader

from app.config import ConfigError, ocr_settings, settings
from app.providers.model_client import get_client
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


class VisionProvider:
    """Primary path: a vision-capable chat-completions model, called
    through this role's configured OpenAI-compatible client, with the
    custom transcription prompt (prompts/ingestion/ocr_transcribe.md).
    Constructed with its own client + model, injected from
    `ocr_settings` — never shared with the generation or embedding
    roles' clients.

    Real implementation — not exercised against a live server in this
    environment (see AGENT_TASKS.md). Swap in once an OCR-capable vision
    model is being served at `ocr_settings.base_url` under
    `ocr_settings.model`.

    Requests the strictest structured-output mode available and falls
    back to the looser `json_object` mode on a 400, same as
    generation_service.GenerationProvider — not every OpenAI-compatible
    vision-capable server supports json_schema mode.
    """

    def __init__(self, client: openai.OpenAI, model: str):
        self._client = client
        self._model = model

    def extract_page(self, pdf_path: Path, page_number: int) -> PageExtractionResult:
        from app.services.pdf_render import render_page_to_png_base64

        image_b64 = render_page_to_png_base64(pdf_path, page_number)
        prompt_spec = get_prompt("ingestion/ocr_transcribe")
        rendered_prompt = prompt_spec.render()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": rendered_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ]

        try:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=prompt_spec.temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": "page_extraction", "schema": prompt_spec.schema, "strict": True},
                    },
                )
            except openai.BadRequestError:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=prompt_spec.temperature,
                    response_format={"type": "json_object"},
                )
            raw = response.choices[0].message.content or ""
            parsed = json_repair.repair_json(raw)
            text = parsed["text"]
        except (openai.OpenAIError, json_repair.JSONRepairError, KeyError) as exc:
            raise OCRExtractionError(f"Vision OCR failed on page {page_number}: {exc}") from exc

        if not text or not text.strip():
            raise OCRExtractionError(f"Vision OCR returned empty text on page {page_number}")

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

    There is no GPU / running inference server / vision model weights
    available in this build environment, so this shim substitutes
    `PyPDFFallbackProvider`'s text while presenting it to the pipeline as
    if the primary vision path had succeeded. That's what lets the *rest*
    of the pipeline (per-page summary/keyword calls, incremental
    doc-summary folding, embeddings, checkpointing/retry, retrieval,
    scenario classification) run and be tested end-to-end without a GPU.

    This means MOCK_MODE demos will not exhibit the real "fallback ⇒ N/A
    enrichment" behavior for OCR-recoverable pages, because every page
    looks like a vision-model success. Do not mistake this for
    validation of the real OCR path — see AGENT_TASKS.md "Wire up real
    model providers".
    """

    def __init__(self) -> None:
        self._fallback = PyPDFFallbackProvider()

    def extract_page(self, pdf_path: Path, page_number: int) -> PageExtractionResult:
        return self._fallback.extract_page(pdf_path, page_number)


def get_primary_ocr_provider() -> OCRProvider:
    if settings.MOCK_MODE:
        return DevShimVLMProvider()
    if not ocr_settings.base_url or not ocr_settings.model:
        raise ConfigError("MOCK_MODE is False but OCR_BASE_URL/OCR_MODEL are not set — see .env.example.")
    return VisionProvider(client=get_client(ocr_settings), model=ocr_settings.model)


def get_fallback_ocr_provider() -> OCRProvider:
    return PyPDFFallbackProvider()

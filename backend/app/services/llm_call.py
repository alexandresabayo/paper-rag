"""Convenience wrapper: render a named prompt and run it through the
configured generation provider. Every ingestion/research call site that
needs a text LLM (i.e. everything except the OCR/VLM path, which needs
images too — see ocr_service.py) goes through this single function."""

from __future__ import annotations

from typing import Any

from app.services.generation_service import get_generation_provider
from app.services.prompt_loader import get_prompt


def run_prompt(name: str, **variables: Any) -> dict[str, Any]:
    spec = get_prompt(name)
    rendered = spec.render(**variables)
    provider = get_generation_provider()
    return provider.generate(prompt=rendered, model=spec.model, temperature=spec.temperature, schema=spec.schema)

"""Convenience wrapper: render a named prompt and run it through the
configured generation-role provider. Every ingestion/research call site
that needs a text LLM (i.e. everything except the OCR/vision path, which
needs images too and uses the separate 'ocr' role — see ocr_service.py)
goes through this single function.

`model` is no longer passed here at all — `get_generation_provider()`
already binds it (from `generation_settings.model`) into whichever
provider it returns, mock or real, so this function only ever needs to
pass the per-prompt `temperature`/`schema`."""

from __future__ import annotations

from typing import Any

from app.services.generation_service import get_generation_provider
from app.services.prompt_loader import get_prompt


def run_prompt(name: str, **variables: Any) -> dict[str, Any]:
    spec = get_prompt(name)
    rendered = spec.render(**variables)
    provider = get_generation_provider()
    return provider.generate(prompt=rendered, temperature=spec.temperature, schema=spec.schema)

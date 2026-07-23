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

from typing import Any, Iterator

from app.services.generation_service import get_generation_provider
from app.services.prompt_loader import get_prompt


def run_prompt(name: str, **variables: Any) -> dict[str, Any]:
    spec = get_prompt(name)
    rendered = spec.render(**variables)
    provider = get_generation_provider()
    return provider.generate(prompt=rendered, temperature=spec.temperature, schema=spec.schema)


def run_prompt_stream(name: str, **variables: Any) -> Iterator[str]:
    """Streaming counterpart to `run_prompt` (ISSUE-015, AGENT_TASKS.md).
    Renders the exact same prompt file/variables, but calls the
    provider's schema-less `generate_stream` instead of `generate` - see
    `generation_service.py`'s module docstring for why streaming and
    schema-constraint don't mix here. Only `research/answer_generation`
    and `research/direct_model` call this; every ingestion prompt keeps
    using `run_prompt` above, since their structured outputs are
    consumed by the pipeline, never streamed to a person."""
    spec = get_prompt(name)
    rendered = spec.render(**variables)
    provider = get_generation_provider()
    yield from provider.generate_stream(prompt=rendered, temperature=spec.temperature)

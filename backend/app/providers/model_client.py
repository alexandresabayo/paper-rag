"""
Generic OpenAI-compatible model client factory.

Every self-hosted or hosted model role (OCR/vision, generation, embedding)
speaks the OpenAI API surface (`/v1/chat/completions`, `/v1/embeddings`)
either natively (OpenAI, Mistral) or via an OpenAI-compatible shim
(Ollama, vLLM, TEI, ...). Provider classes in `app/services/*_service.py`
each get their own `openai.OpenAI` client instance from `get_client()`,
scoped to that role's `ProviderSettings` (see app/config.py) - there is no
shared/global client, since OCR, generation, and embedding commonly point
at different hosts, keys, or providers at the same time.

Not exercised against a live server in this environment - see
AGENT_TASKS.md.
"""

from __future__ import annotations

import openai

from app.config import ProviderSettings


def get_client(settings: ProviderSettings) -> openai.OpenAI:
    """Build a fresh OpenAI SDK client for one model role.

    Call once per provider instance (see `get_*_provider()` in the
    relevant `app/services/*_service.py`) - never share one client across
    roles. Assumes the caller has already validated `settings.base_url`
    is set (the `get_*_provider()` factories do this, raising
    `app.config.ConfigError` before ever reaching here) - this function
    itself stays simple and does no validation of its own.
    """
    return openai.OpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout=settings.timeout_seconds,
    )

"""
Ollama HTTP client.

Every self-hosted model in the stack (OCR/VLM, generation, embeddings) is
served through Ollama (PRD Section 5), so this is the one place that speaks
HTTP to it. Provider classes in `app/services/*_service.py` call this
client; they don't build requests themselves.

Not exercised in MOCK_MODE (the default) — see app/config.py and
AGENT_TASKS.md for going from mock to a real, running Ollama instance.
This module's request/response shapes are written against Ollama's
`/api/generate` and `/api/embed` endpoints as of early 2026; re-verify
against `ollama --version`'s docs when wiring this up for real, since this
code has not been exercised against a live server in this environment.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        images_base64: list[str] | None = None,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Returns the raw text of the `response` field. Caller is
        responsible for JSON-parsing it (with json_repair as a fallback)
        when a schema was requested."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if images_base64:
            payload["images"] = images_base64
        if json_schema is not None:
            payload["format"] = json_schema

        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama /api/generate call failed for model={model!r}: {exc}") from exc

        data = response.json()
        try:
            return data["response"]
        except KeyError as exc:
            raise OllamaError(f"Unexpected Ollama response shape: {data!r}") from exc

    def embed(self, *, model: str, texts: list[str]) -> list[list[float]]:
        payload = {"model": model, "input": texts}
        try:
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama /api/embed call failed for model={model!r}: {exc}") from exc

        data = response.json()
        try:
            return data["embeddings"]
        except KeyError as exc:
            raise OllamaError(f"Unexpected Ollama embed response shape: {data!r}") from exc

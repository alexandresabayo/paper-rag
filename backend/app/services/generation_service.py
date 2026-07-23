"""
Generation provider — role-scoped, OpenAI-SDK based (see
app/providers/model_client.py and `generation_settings` in app/config.py).
Section 9 (schema-constrained structured output, with `json_repair` as the
documented fallback for genuine edge cases).

Every prompt file under prompts/ declares a `schema` in its frontmatter
(app/services/prompt_loader.py). `model` no longer lives in the prompt
file — it's resolved from `generation_settings.model` once, when the
provider is constructed (see `get_generation_provider()` / callers in
app/services/llm_call.py), so the same prompt can be pointed at any
generation-role provider without editing it.

`generate_stream()` (ISSUE-015, AGENT_TASKS.md) is deliberately
schema-less, unlike `generate()`. A JSON-schema-constrained response
(`{"type": "json_schema", ...}`) streams back as raw, partial JSON text
(`{"ans`, then `wer": "Hel`, ...) - not something that can be shown to a
person token-by-token without incrementally parsing partial JSON, which
is fragile and out of proportion to what's actually needed here: every
prompt that ever calls `generate_stream` has a single-string schema
(`{"answer": <string>}`), so an *unconstrained* streaming completion's
raw output already IS the answer text, with no wrapper to strip. Schema
mode stays the default for every other call in this app (ingestion's
structured extraction, and even the non-streaming answer path if it's
ever needed again) - this is a narrow, deliberate exception for the one
call site whose entire output is prose meant to be watched as it's
written.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterator, Protocol

import openai

from app.config import ConfigError, generation_settings, settings
from app.providers.model_client import get_client
from app.services import json_repair

# Field names that hold the "main content" of a response, worth a slightly
# more legible mock than a bare hash — purely cosmetic, for a nicer local
# demo experience in MOCK_MODE.
_PROSE_FIELD_NAMES = {"answer", "summary", "running_summary", "text"}


class GenerationProviderProtocol(Protocol):
    def generate(self, *, prompt: str, temperature: float, schema: dict[str, Any]) -> dict[str, Any]: ...
    def generate_stream(self, *, prompt: str, temperature: float) -> Iterator[str]: ...


class GenerationProvider:
    """Real implementation against this role's configured
    OpenAI-compatible `/v1/chat/completions` endpoint. Constructed with
    its own client + model, injected from `generation_settings` — never
    shared with the OCR or embedding roles' clients, and symmetrical with
    `VisionProvider`/`EmbeddingProvider`, which bind their model the same
    way.

    Requests the strictest structured-output mode the OpenAI SDK exposes
    (`response_format={"type": "json_schema", ...}`) and falls back to
    the looser `{"type": "json_object"}` mode on a 400 — not every
    OpenAI-compatible server (vLLM, Ollama's compat layer, ...) supports
    the newer json_schema mode yet. `json_repair` remains the
    last-resort net for whatever gets through malformed either way
    (Section 3/9).

    Not exercised against a live server in this environment — see
    AGENT_TASKS.md.
    """

    def __init__(self, client: openai.OpenAI, model: str):
        self._client = client
        self._model = model

    def generate(self, *, prompt: str, temperature: float, schema: dict[str, Any]) -> dict[str, Any]:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "response", "schema": schema, "strict": True},
                },
            )
        except openai.BadRequestError:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
            except openai.OpenAIError as exc:
                raise ConfigError(f"Generation call failed for model={self._model!r}: {exc}") from exc
        except openai.OpenAIError as exc:
            raise ConfigError(f"Generation call failed for model={self._model!r}: {exc}") from exc

        raw = response.choices[0].message.content or ""
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            # Structured-output modes should make this rare — Section 9
            # keeps json_repair around for exactly this "genuine edge
            # case".
            return json_repair.repair_json(raw)

    def generate_stream(self, *, prompt: str, temperature: float) -> Iterator[str]:
        """Unconstrained streaming completion - see the module docstring
        for why this doesn't take (or want) a schema. Yields raw text
        deltas as they arrive; the caller (`app/routers/research.py`)
        forwards each one straight through as an SSE `chunk` event."""
        messages = [{"role": "user", "content": prompt}]
        try:
            stream = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
        except openai.OpenAIError as exc:
            raise ConfigError(f"Streaming generation call failed for model={self._model!r}: {exc}") from exc

        for chunk in stream:
            if not chunk.choices:
                continue  # some servers send a final usage-only chunk with an empty choices list
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class MockGenerationProvider:
    """Schema-aware placeholder generator: walks the requested JSON schema
    and fills in deterministic, structurally-valid placeholder values, so
    every call site (metadata, page summary, keywords, doc-summary fold,
    research answers) gets a shape-correct response without a running
    model. Takes no constructor arguments — a mock has no real model to
    bind, unlike `GenerationProvider`."""

    def generate(self, *, prompt: str, temperature: float, schema: dict[str, Any]) -> dict[str, Any]:
        seed = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]
        return self._fill(schema, seed=seed, prompt_excerpt=prompt[:160])

    def generate_stream(self, *, prompt: str, temperature: float) -> Iterator[str]:
        """Same placeholder phrasing as the non-streaming mock's "answer"
        field (`_PROSE_FIELD_NAMES` below), just delivered word-by-word so
        the streaming path is exercisable end-to-end without a GPU (every
        automated test in this repo runs in MOCK_MODE - see
        tests/conftest.py)."""
        text = f"[MOCK_MODE placeholder — no LLM connected] Stand-in answer for prompt starting: {prompt[:160]!r}"
        for word in text.split(" "):
            yield word + " "

    def _fill(self, node: dict[str, Any], *, seed: str, prompt_excerpt: str, path: str = "") -> Any:
        node_type = node.get("type", "string")

        if node_type == "object":
            return {
                key: self._fill(child, seed=f"{seed}:{key}", prompt_excerpt=prompt_excerpt, path=f"{path}.{key}")
                for key, child in node.get("properties", {}).items()
            }

        if node_type == "array":
            item_schema = node.get("items", {"type": "string"})
            count = 2
            return [
                self._fill(item_schema, seed=f"{seed}:{i}", prompt_excerpt=prompt_excerpt, path=f"{path}[{i}]")
                for i in range(count)
            ]

        if node_type == "string":
            if "enum" in node and node["enum"]:
                index = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(node["enum"])
                return node["enum"][index]
            field_name = path.rsplit(".", 1)[-1].split("[")[0]
            if field_name in _PROSE_FIELD_NAMES:
                return (
                    f"[MOCK_MODE placeholder — no LLM connected] Stand-in {field_name} for prompt "
                    f"starting: {prompt_excerpt!r}"
                )
            digest = hashlib.sha256(seed.encode()).hexdigest()[:6]
            return f"mock-{field_name or 'value'}-{digest}"

        return None


def get_generation_provider() -> GenerationProviderProtocol:
    if settings.MOCK_MODE:
        return MockGenerationProvider()
    if not generation_settings.base_url or not generation_settings.model:
        raise ConfigError(
            "MOCK_MODE is False but GENERATION_BASE_URL/GENERATION_MODEL are not set — see .env.example."
        )
    return GenerationProvider(client=get_client(generation_settings), model=generation_settings.model)

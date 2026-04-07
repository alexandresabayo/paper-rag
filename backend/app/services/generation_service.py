"""
Generation providers — PRD Section 5 (`Mistral Small`/`Large 3`, served
through Ollama) and Section 9 (schema-constrained structured output, with
`json_repair` as the documented fallback for genuine edge cases).

Every prompt file under prompts/ declares a `schema` in its frontmatter
(app/services/prompt_loader.py), so `generate()` always returns a parsed
`dict` matching that schema's top-level properties — callers never handle
raw text.
"""

from __future__ import annotations

import hashlib
from typing import Any, Protocol

from app.config import settings
from app.providers.ollama_client import OllamaClient
from app.services import json_repair

# Field names that hold the "main content" of a response, worth a slightly
# more legible mock than a bare hash — purely cosmetic, for a nicer local
# demo experience in MOCK_MODE.
_PROSE_FIELD_NAMES = {"answer", "summary", "running_summary", "text"}


class GenerationProvider(Protocol):
    def generate(self, *, prompt: str, model: str, temperature: float, schema: dict[str, Any]) -> dict[str, Any]: ...


class OllamaGenerationProvider:
    """Real implementation. Not exercised against a live server in this
    environment — see AGENT_TASKS.md."""

    def __init__(self, client: OllamaClient | None = None):
        self._client = client or OllamaClient()

    def generate(self, *, prompt: str, model: str, temperature: float, schema: dict[str, Any]) -> dict[str, Any]:
        raw = self._client.generate(
            model=model,
            prompt=prompt,
            json_schema=schema,
            temperature=temperature,
        )
        try:
            import json

            return json.loads(raw)
        except (ValueError, TypeError):
            # Ollama's JSON-mode should make this rare — Section 9 keeps
            # json_repair around for exactly this "genuine edge case".
            return json_repair.repair_json(raw)


class MockGenerationProvider:
    """Schema-aware placeholder generator: walks the requested JSON schema
    and fills in deterministic, structurally-valid placeholder values, so
    every call site (metadata, page summary, keywords, doc-summary fold,
    research answers) gets a shape-correct response without a running
    model."""

    def generate(self, *, prompt: str, model: str, temperature: float, schema: dict[str, Any]) -> dict[str, Any]:
        seed = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:10]
        return self._fill(schema, seed=seed, prompt_excerpt=prompt[:160])

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


def get_generation_provider() -> GenerationProvider:
    if settings.MOCK_MODE:
        return MockGenerationProvider()
    return OllamaGenerationProvider()

"""
JSON parsing fallback for malformed LLM/VLM structured-output responses.

Ollama's schema-constrained `format` parameter (Section 9) should make this
fire rarely, but it doesn't guarantee perfectly parseable JSON on every
model/quantization — this is the safety net described in Section 3, not the
primary mechanism.
"""

from __future__ import annotations

import json
import re
from typing import Any


class JSONRepairError(ValueError):
    """Raised when even the fallback strategies can't recover valid JSON."""


def _strip_code_fences(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return fenced.group(1) if fenced else text


def _extract_outermost_braces(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _quote_unquoted_keys(text: str) -> str:
    # foo: "bar"  ->  "foo": "bar"   (only for keys that aren't already quoted)
    return re.sub(r"(?<=[{,]\s)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'"\1":', text)


def repair_json(raw_text: str) -> dict[str, Any]:
    """Best-effort parse of `raw_text` as a JSON object.

    Tries, in order: (1) parse as-is, (2) strip markdown code fences, (3)
    slice to the outermost `{...}` span, (4) remove trailing commas, (5)
    quote bareword keys. Raises JSONRepairError if nothing works, so the
    caller can decide how to degrade (e.g. leave a field N/A rather than
    crash the whole pipeline task).
    """
    candidates = [raw_text]

    stripped = _strip_code_fences(raw_text).strip()
    if stripped != raw_text:
        candidates.append(stripped)

    sliced = _extract_outermost_braces(stripped)
    if sliced:
        candidates.append(sliced)
        candidates.append(_remove_trailing_commas(sliced))
        candidates.append(_quote_unquoted_keys(_remove_trailing_commas(sliced)))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed

    raise JSONRepairError(f"Could not recover a JSON object from model output: {raw_text[:200]!r}")

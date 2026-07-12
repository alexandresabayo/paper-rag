"""
Prompt loader — PRD Section 9.

Every LLM/VLM call site loads its prompt from a versioned `.md` file under
`prompts/`, never an inline string. Each file pairs a Jinja2 template body
with YAML frontmatter declaring `temperature` and (optionally) `schema` —
the JSON schema passed straight to the configured provider's
structured-output request.

`model` is deliberately *not* declared here: a prompt is provider-agnostic
by design, and which model actually serves it is a runtime choice
(`ocr_settings.model` / `generation_settings.model`, see
app/config.py) — not a property of the prompt text. Call sites request a
prompt **by name** (e.g. `"ingestion/page_summary"`) and pass template
variables; they never touch prompt text directly. This is the "thin
loader" described in Section 9.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined

from app.config import settings

_FRONTMATTER_DELIMITER = "---"

_jinja_env = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


@dataclass(frozen=True)
class PromptSpec:
    name: str
    temperature: float
    schema: dict[str, Any] | None
    template_source: str

    def render(self, **variables: Any) -> str:
        template = _jinja_env.from_string(self.template_source)
        return template.render(**variables).strip()


class PromptNotFoundError(FileNotFoundError):
    pass


class PromptFormatError(ValueError):
    pass


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    lines = raw.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        raise PromptFormatError("Prompt file must start with a '---' YAML frontmatter block.")
    try:
        end_index = next(i for i in range(1, len(lines)) if lines[i].strip() == _FRONTMATTER_DELIMITER)
    except StopIteration as exc:
        raise PromptFormatError("Unterminated YAML frontmatter block (missing closing '---').") from exc

    frontmatter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    frontmatter = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(frontmatter, dict):
        raise PromptFormatError("Frontmatter must be a YAML mapping.")
    return frontmatter, body


@functools.lru_cache(maxsize=None)
def _load_spec(name: str) -> PromptSpec:
    """`name` is a slash-separated path relative to PROMPTS_DIR, without the
    `.md` extension, e.g. `"research/answer_generation"`."""
    path: Path = settings.PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise PromptNotFoundError(f"No prompt file at {path}")

    frontmatter, body = _split_frontmatter(path.read_text(encoding="utf-8"))

    missing = {"temperature"} - frontmatter.keys()
    if missing:
        raise PromptFormatError(f"{path} frontmatter missing required key(s): {sorted(missing)}")

    return PromptSpec(
        name=name,
        temperature=float(frontmatter["temperature"]),
        schema=frontmatter.get("schema"),
        template_source=body,
    )


def get_prompt(name: str) -> PromptSpec:
    """Public entry point. Cached — the file is parsed once per process.

    Call `clear_cache()` (used by tests) if a prompt file changes on disk
    mid-process."""
    return _load_spec(name)


def clear_cache() -> None:
    _load_spec.cache_clear()

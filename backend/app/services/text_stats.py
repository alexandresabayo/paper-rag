"""Small, dependency-free text heuristics used by the ingestion pipeline."""

from __future__ import annotations

import re

_SENTENCE_BOUNDARY = re.compile(r"[.!?]+(?:\s|$)")


def count_sentences(text: str | None) -> int:
    """Rough sentence count via terminal-punctuation boundaries.

    Good enough for the "is this page too short to summarize meaningfully"
    check (PRD Section 3) — not intended as a linguistic sentence
    tokenizer. Swap in a real tokenizer later if this proves too coarse for
    a given corpus (see AGENT_TASKS.md).
    """
    if not text or not text.strip():
        return 0
    matches = _SENTENCE_BOUNDARY.findall(text.strip())
    if matches:
        return len(matches)
    # No terminal punctuation found at all — treat as a single sentence if
    # there's any non-trivial content, so short titles/labels don't get
    # miscounted as zero.
    return 1 if len(text.strip()) > 0 else 0

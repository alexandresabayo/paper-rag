"""Turns the structured keyword-categories dict (PRD Section 4 "Keyword
Categories") into a single text blob suitable for embedding — the
embedding model takes text, not JSON."""

from __future__ import annotations

from typing import Any


def flatten_keywords_for_embedding(keywords: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in ("core_topics", "related_concepts", "domain_terms", "operational_verbs", "entities", "general_keywords"):
        values = keywords.get(field) or []
        parts.extend(str(v) for v in values)
    for acronym_entry in keywords.get("acronyms") or []:
        acronym = acronym_entry.get("acronym", "")
        expansion = acronym_entry.get("expansion", "")
        parts.append(f"{acronym} ({expansion})".strip())
    return ", ".join(p for p in parts if p)

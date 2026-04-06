"""
Language detection — PRD 2.A #3.

Scoped to French/English/Spanish per the PRD's Core Concept (Section 1):
BGE-M3's embedding space and the generation model both handle FR/EN/ES
transparently at query time (2.B #3), so detection here exists to *record*
each document's language (Section 4 Document.Language), not to drive any
branching logic elsewhere in the app.
"""

from __future__ import annotations

import functools

from lingua import Language, LanguageDetectorBuilder

_SUPPORTED_LANGUAGES = [Language.ENGLISH, Language.FRENCH, Language.SPANISH]


@functools.lru_cache(maxsize=1)
def _detector():
    # Built once per process — lingua's model loading isn't free.
    return LanguageDetectorBuilder.from_languages(*_SUPPORTED_LANGUAGES).build()


def detect_language(text: str) -> str | None:
    """Returns a lowercase ISO 639-1 code ('en' | 'fr' | 'es'), or None if
    the detector isn't confident enough to call it (e.g. very short or
    non-linguistic text)."""
    if not text or not text.strip():
        return None
    result = _detector().detect_language_of(text)
    if result is None:
        return None
    return result.iso_code_639_1.name.lower()

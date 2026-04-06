"""
Corrupted-text detection and repair (PRD 2.A #10, Section 3 "Character
Encoding Issues").

Two independent things happen here:

1. `looks_corrupted()` — a cheap heuristic to flag text worth reporting in
   the ingestion dashboard's data-quality view, even after a "successful"
   extraction (e.g. a PDF with a broken embedded font table can still
   produce garbled text via the pypdf fallback path).
2. `fix_mojibake()` — a replacement table for the most common UTF-8-read-
   as-Latin-1 (and similar) mis-decodes, e.g. "Ã©" -> "é", curly quotes
   turned into "â€™", etc.

Both are intentionally simple, table-driven, and dependency-free — this is
a repair pass over already-decoded `str` text, not a charset-detection
library. Extend `_MOJIBAKE_TABLE` as new corruption patterns show up in
real corpora (see AGENT_TASKS.md).
"""

from __future__ import annotations

import re

# Common UTF-8 bytes mis-decoded as Latin-1/Windows-1252 and re-encoded to
# UTF-8 — the classic "double encoding" mojibake pattern. Ordered so longer,
# more specific sequences are replaced before shorter ones that could be a
# substring of another entry.
_MOJIBAKE_TABLE: list[tuple[str, str]] = [
    ("â€™", "\u2019"),  # '
    ("â€˜", "\u2018"),  # '
    ("â€œ", "\u201c"),  # "
    ("â€\x9d", "\u201d"),  # "
    ("â€“", "\u2013"),  # –
    ("â€”", "\u2014"),  # —
    ("â€¦", "\u2026"),  # …
    ("â€¢", "\u2022"),  # •
    ("Ã©", "é"),
    ("Ã¨", "è"),
    ("Ã«", "ë"),
    ("Ã¯", "ï"),
    ("Ã¹", "ù"),
    ("Ã¢", "â"),
    ("Ã®", "î"),
    ("Ã´", "ô"),
    ("Ã»", "û"),
    ("Ã§", "ç"),
    ("Ã±", "ñ"),
    ("Ã¡", "á"),
    ("Ã­", "í"),
    ("Ã³", "ó"),
    ("Ãº", "ú"),
    ("Ã¼", "ü"),
    ("â€š", ","),
    ("Â«", "\u00ab"),  # «
    ("Â»", "\u00bb"),  # »
    ("Â°", "\u00b0"),  # °
    ("Â ", " "),  # stray non-breaking-space artifact
    ("\ufffd", ""),  # literal replacement character -> drop
]

# A run of the Unicode replacement character, or of the mojibake lead bytes
# "Ã"/"â€" beyond a small number of occurrences, indicates the extraction
# itself is unreliable enough to flag for the dashboard, even after
# `fix_mojibake` has run.
_CORRUPTION_MARKERS = re.compile(r"[\ufffd]|(?:Ã.){3,}|(?:â€.){3,}")


def fix_mojibake(text: str) -> tuple[str, bool]:
    """Returns (fixed_text, was_changed)."""
    fixed = text
    for corrupted, correct in _MOJIBAKE_TABLE:
        fixed = fixed.replace(corrupted, correct)
    return fixed, fixed != text


def looks_corrupted(text: str) -> bool:
    """Heuristic flag for the data-quality report — not a hard failure."""
    if not text:
        return False
    if _CORRUPTION_MARKERS.search(text):
        return True
    # A very high ratio of non-printable/control characters is also a sign
    # of a bad extraction (e.g. embedded-font glyph-index soup).
    control_chars = sum(1 for ch in text if ord(ch) < 32 and ch not in "\n\r\t")
    return len(text) > 0 and (control_chars / len(text)) > 0.02

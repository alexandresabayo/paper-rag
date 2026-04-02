"""
Primary-key generation (PRD 2.A #11).

Documents are keyed by a hash of their file bytes (stable across re-uploads
of the same file, and a natural dedupe key). Pages are keyed by
`{document_id}:{page_number}`.
"""

from __future__ import annotations

import hashlib


def compute_document_id(file_bytes: bytes) -> str:
    """SHA-256 of the raw PDF bytes, hex-encoded. Stable, content-addressed."""
    return hashlib.sha256(file_bytes).hexdigest()


def make_page_id(document_id: str, page_number: int) -> str:
    """`page_number` is 1-indexed."""
    return f"{document_id}:{page_number:05d}"

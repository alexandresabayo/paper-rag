"""
Data quality validation — PRD 2.A #9 ("Data Quality Validation... generate
control reports").

Computed on demand from the current state of `documents`/`pages` rather
than persisted as its own table: the underlying facts (status, N/A
metadata, fallback usage, encoding fixes) are already stored on the rows
themselves, so a report is just a read-time aggregation. Revisit if the
dashboard needs historical trend charts across many report snapshots
(see AGENT_TASKS.md) — that would need actual persistence.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def generate_quality_report(conn: sqlite3.Connection) -> dict[str, Any]:
    totals = conn.execute(
        """
        SELECT
            COUNT(*) AS total_documents,
            COALESCE(SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END), 0) AS documents_done,
            COALESCE(SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END), 0) AS documents_processing,
            COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END), 0) AS documents_failed,
            COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) AS documents_pending,
            COALESCE(SUM(CASE WHEN metadata_status = 'na' THEN 1 ELSE 0 END), 0) AS documents_with_na_metadata
        FROM documents
        """
    ).fetchone()

    page_totals = conn.execute(
        """
        SELECT
            COUNT(*) AS total_pages,
            COALESCE(SUM(CASE WHEN processing_status = 'failed' THEN 1 ELSE 0 END), 0) AS pages_failed,
            COALESCE(SUM(CASE WHEN extractor_used = 'fallback' THEN 1 ELSE 0 END), 0) AS pages_used_fallback,
            COALESCE(SUM(CASE WHEN content_text_fixed = 1 THEN 1 ELSE 0 END), 0) AS pages_with_encoding_fixes,
            COALESCE(SUM(CASE WHEN is_short_page = 1 THEN 1 ELSE 0 END), 0) AS pages_short,
            COALESCE(SUM(CASE WHEN content_text IS NULL OR content_text = '' THEN 1 ELSE 0 END), 0) AS pages_missing_content
        FROM pages
        """
    ).fetchone()

    failed_documents = conn.execute(
        "SELECT id, file_name, last_error FROM documents WHERE status = 'failed' ORDER BY updated_at DESC LIMIT 50"
    ).fetchall()

    failed_pages = conn.execute(
        """
        SELECT document_id, page_number, error_message
        FROM pages
        WHERE processing_status = 'failed'
        ORDER BY updated_at DESC
        LIMIT 100
        """
    ).fetchall()

    na_metadata_documents = conn.execute(
        "SELECT id, file_name FROM documents WHERE metadata_status = 'na' ORDER BY updated_at DESC LIMIT 50"
    ).fetchall()

    return {
        "documents": dict(totals),
        "pages": dict(page_totals),
        "failed_documents": [dict(r) for r in failed_documents],
        "failed_pages": [dict(r) for r in failed_pages],
        "na_metadata_documents": [dict(r) for r in na_metadata_documents],
    }

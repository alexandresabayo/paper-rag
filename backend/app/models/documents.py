"""
Document & page persistence.

Raw SQL rather than an ORM — deliberate, not an oversight: the PRD's stack
(Section 5) is chosen throughout for being small, single-purpose, and
community-governed rather than defaulting to the heaviest common tool
(a separate vector DB, a message broker, ...). An ORM would also sit
awkwardly on top of sqlite-vec's virtual tables. Every function here takes
an open `sqlite3.Connection` and does not commit — callers control
transaction boundaries (see `app.database.session`).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.utils.hashing import make_page_id


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------


def create_document(conn: sqlite3.Connection, *, document_id: str, file_name: str, file_path: str, total_pages: int) -> None:
    conn.execute(
        """
        INSERT INTO documents (id, file_name, file_path, total_pages, status, metadata_status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'pending', 'pending', ?, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (document_id, file_name, file_path, total_pages, _now(), _now()),
    )


def create_pages(conn: sqlite3.Connection, *, document_id: str, total_pages: int) -> None:
    rows = [(make_page_id(document_id, n), document_id, n, _now(), _now()) for n in range(1, total_pages + 1)]
    conn.executemany(
        """
        INSERT INTO pages (id, document_id, page_number, processing_status, created_at, updated_at)
        VALUES (?, ?, ?, 'pending', ?, ?)
        ON CONFLICT(document_id, page_number) DO NOTHING
        """,
        rows,
    )


def get_document(conn: sqlite3.Connection, document_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    return dict(row) if row else None


def list_documents(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            d.*,
            COUNT(p.id) AS total_page_rows,
            SUM(CASE WHEN p.processing_status = 'done' THEN 1 ELSE 0 END) AS pages_done,
            SUM(CASE WHEN p.processing_status = 'failed' THEN 1 ELSE 0 END) AS pages_failed,
            SUM(CASE WHEN p.extractor_used = 'fallback' THEN 1 ELSE 0 END) AS pages_used_fallback,
            SUM(CASE WHEN p.content_text_fixed = 1 THEN 1 ELSE 0 END) AS pages_with_encoding_fixes
        FROM documents d
        LEFT JOIN pages p ON p.document_id = d.id
        GROUP BY d.id
        ORDER BY d.created_at DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def update_document_fields(conn: sqlite3.Connection, document_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": _now()}
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE documents SET {set_clause} WHERE id = ?", (*fields.values(), document_id))


def set_document_metadata(
    conn: sqlite3.Connection,
    document_id: str,
    *,
    doc_type: str | None,
    authors: list[str] | None,
    year: str | None,
    title: str | None,
    venue: str | None,
    doi: str | None,
    acronym: str | None,
    metadata_status: str,
    edited_by_admin: bool = False,
) -> None:
    update_document_fields(
        conn,
        document_id,
        doc_type=doc_type,
        authors_json=json.dumps(authors) if authors is not None else None,
        year=year,
        title=title,
        venue=venue,
        doi=doi,
        acronym=acronym,
        metadata_status=metadata_status,
        metadata_edited_by_admin=1 if edited_by_admin else 0,
    )


# ---------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------


def get_page(conn: sqlite3.Connection, document_id: str, page_number: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM pages WHERE document_id = ? AND page_number = ?",
        (document_id, page_number),
    ).fetchone()
    return dict(row) if row else None


def list_pages(conn: sqlite3.Connection, document_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM pages WHERE document_id = ? ORDER BY page_number ASC",
        (document_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_page_fields(conn: sqlite3.Connection, page_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields = {**fields, "updated_at": _now()}
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE pages SET {set_clause} WHERE id = ?", (*fields.values(), page_id))


def get_resume_page_number(conn: sqlite3.Connection, document_id: str) -> int | None:
    """The checkpoint a retry resumes from (PRD 2.A #12): the lowest
    page_number that is NOT 'done'. None if every page is done."""
    row = conn.execute(
        """
        SELECT MIN(page_number) AS resume_from
        FROM pages
        WHERE document_id = ? AND processing_status != 'done'
        """,
        (document_id,),
    ).fetchone()
    return row["resume_from"] if row and row["resume_from"] is not None else None


def get_done_page_summaries_before(conn: sqlite3.Connection, document_id: str, before_page_number: int) -> list[tuple[int, str]]:
    """Ordered (page_number, page_summary) for already-done pages before
    `before_page_number` that actually have a summary (i.e. excludes
    fallback/short-page N/A pages) — used to cheaply rebuild
    documents.running_summary on resume (PRD 2.A #5), without re-running
    any VLM OCR."""
    rows = conn.execute(
        """
        SELECT page_number, page_summary
        FROM pages
        WHERE document_id = ?
          AND page_number < ?
          AND processing_status = 'done'
          AND page_summary IS NOT NULL
        ORDER BY page_number ASC
        """,
        (document_id, before_page_number),
    ).fetchall()
    return [(r["page_number"], r["page_summary"]) for r in rows]

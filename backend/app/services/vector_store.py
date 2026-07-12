"""
sqlite-vec read/write helpers.

Each vec0 table's `rowid` is reused directly from the corresponding
`pages`/`documents` row (see schema_core.sql's header comment) — there is
no separate identity for vectors. vec0 tables in the installed sqlite-vec
version support plain `UPDATE ... WHERE rowid = ?` but *not*
`INSERT OR REPLACE` (it still trips the rowid uniqueness check), so
`upsert_vector` tries INSERT first and falls back to UPDATE — this matters
because a retried/re-ingested page must overwrite its old vectors, not
duplicate or reject.

Schema lifecycle: the four vec0 tables don't necessarily exist yet — they
are created lazily (see `app.database.ensure_vector_schema`) the first
time `upsert_vector` is ever called on a given DB file, sized from that
call's real vector. Every read helper here (`search`, `table_row_count`,
`delete_vector`) therefore treats "table doesn't exist" as a normal,
expected state (nothing has been embedded into this DB yet) rather than
an error - e.g. `search()` on a brand-new, never-ingested-into DB returns
an empty result list, not an exception, which is what lets
retrieval_service.retrieve_pages() naturally resolve to the "model_only"
scenario for an empty corpus.
"""

from __future__ import annotations

import sqlite3
import struct

_VALID_TABLES = {"page_content_vec", "page_summary_vec", "page_keywords_vec", "document_vec"}


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _validate_table(table: str) -> None:
    if table not in _VALID_TABLES:
        raise ValueError(f"Unknown vec table {table!r}, expected one of {_VALID_TABLES}")


def _is_missing_table_error(exc: sqlite3.OperationalError) -> bool:
    return "no such table" in str(exc).lower()


def upsert_vector(conn: sqlite3.Connection, table: str, rowid: int, vector: list[float]) -> None:
    """Insert or overwrite `vector` at `rowid` in `table`.

    Ensures all four vec0 tables exist (sized from `len(vector)`) before
    writing, via `app.database.ensure_vector_schema` — this is the single
    trigger point for lazy vector-schema creation; see that function's
    docstring and the module docstring above for why upsert is the right
    place for it (and not e.g. app/pipeline/tasks.py, which never needs
    to know about schema lifecycle at all as a result).
    """
    _validate_table(table)

    from app.database import ensure_vector_schema

    ensure_vector_schema(conn, dim=len(vector))

    blob = _pack(vector)
    try:
        conn.execute(f"INSERT INTO {table}(rowid, embedding) VALUES (?, ?)", (rowid, blob))
    except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        if "unique constraint failed" not in str(exc).lower():
            raise
        conn.execute(f"UPDATE {table} SET embedding = ? WHERE rowid = ?", (blob, rowid))


def delete_vector(conn: sqlite3.Connection, table: str, rowid: int) -> None:
    _validate_table(table)
    try:
        conn.execute(f"DELETE FROM {table} WHERE rowid = ?", (rowid,))
    except sqlite3.OperationalError as exc:
        if not _is_missing_table_error(exc):
            raise
        # Table doesn't exist yet - nothing was ever embedded into this DB,
        # so there is nothing to delete. Consistent no-op, not an error.


def search(conn: sqlite3.Connection, table: str, query_vector: list[float], k: int) -> list[tuple[int, float]]:
    """Returns [(rowid, cosine_distance), ...] ordered by ascending
    distance (i.e. most similar first). `distance_metric=cosine` on the
    table means distance == 1 - cosine_similarity.

    Returns `[]` (rather than raising) if `table` doesn't exist yet - a
    completely normal state for a DB nothing has been ingested into."""
    _validate_table(table)
    if k <= 0:
        return []
    blob = _pack(query_vector)
    try:
        rows = conn.execute(
            f"SELECT rowid, distance FROM {table} WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (blob, k),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if not _is_missing_table_error(exc):
            raise
        return []
    return [(r["rowid"], r["distance"]) for r in rows]


def table_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Returns 0 (rather than raising) if `table` doesn't exist yet."""
    _validate_table(table)
    try:
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    except sqlite3.OperationalError as exc:
        if not _is_missing_table_error(exc):
            raise
        return 0
    return row["n"]

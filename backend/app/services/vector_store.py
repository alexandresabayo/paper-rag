"""
sqlite-vec read/write helpers.

Each vec0 table's `rowid` is reused directly from the corresponding
`pages`/`documents` row (see schema.sql's header comment) — there is no
separate identity for vectors. vec0 tables in the installed sqlite-vec
version support plain `UPDATE ... WHERE rowid = ?` but *not*
`INSERT OR REPLACE` (it still trips the rowid uniqueness check), so
`upsert_vector` tries INSERT first and falls back to UPDATE — this matters
because a retried/re-ingested page must overwrite its old vectors, not
duplicate or reject.
"""

from __future__ import annotations

import sqlite3
import struct
from typing import Iterable

_VALID_TABLES = {"page_content_vec", "page_summary_vec", "page_keywords_vec", "document_vec"}


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _validate_table(table: str) -> None:
    if table not in _VALID_TABLES:
        raise ValueError(f"Unknown vec table {table!r}, expected one of {_VALID_TABLES}")


def upsert_vector(conn: sqlite3.Connection, table: str, rowid: int, vector: list[float]) -> None:
    _validate_table(table)
    blob = _pack(vector)
    try:
        conn.execute(f"INSERT INTO {table}(rowid, embedding) VALUES (?, ?)", (rowid, blob))
    except (sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        if "unique constraint failed" not in str(exc).lower():
            raise
        conn.execute(f"UPDATE {table} SET embedding = ? WHERE rowid = ?", (blob, rowid))


def delete_vector(conn: sqlite3.Connection, table: str, rowid: int) -> None:
    _validate_table(table)
    conn.execute(f"DELETE FROM {table} WHERE rowid = ?", (rowid,))


def search(conn: sqlite3.Connection, table: str, query_vector: list[float], k: int) -> list[tuple[int, float]]:
    """Returns [(rowid, cosine_distance), ...] ordered by ascending
    distance (i.e. most similar first). `distance_metric=cosine` on the
    table means distance == 1 - cosine_similarity."""
    _validate_table(table)
    if k <= 0:
        return []
    blob = _pack(query_vector)
    rows = conn.execute(
        f"SELECT rowid, distance FROM {table} WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (blob, k),
    ).fetchall()
    return [(r["rowid"], r["distance"]) for r in rows]


def table_row_count(conn: sqlite3.Connection, table: str) -> int:
    _validate_table(table)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return row["n"]

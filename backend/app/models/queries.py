from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def create_query(
    conn: sqlite3.Connection,
    *,
    query_id: str,
    query_text: str,
    response_text: str,
    answer_mode: str,
    scenario: str | None,
    retrieved_pages_json: str,
) -> None:
    conn.execute(
        """
        INSERT INTO queries (id, query_text, response_text, answer_mode, scenario, retrieved_pages_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (query_id, query_text, response_text, answer_mode, scenario, retrieved_pages_json, _now()),
    )


def list_queries(conn: sqlite3.Connection, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM queries ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_query(conn: sqlite3.Connection, query_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,)).fetchone()
    return dict(row) if row else None

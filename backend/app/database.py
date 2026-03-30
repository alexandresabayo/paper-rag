"""
SQLite connection management.

One physical file (see Settings.DB_PATH) holds both the relational tables
and the sqlite-vec virtual tables — "no separate vector database is needed"
per the PRD's stack section. Every connection loads the sqlite-vec
extension so `MATCH` queries against the vec0 tables work.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import sqlite_vec

from app.config import settings

SCHEMA_PATH = Path(__file__).parent / "db" / "schema.sql"


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a new connection. Callers are responsible for closing it (or use
    `session()` below as a context manager)."""
    path = str(db_path or settings.DB_PATH)
    conn = sqlite3.connect(path)
    _configure(conn)
    return conn


@contextmanager
def session(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """Create all tables/virtual tables if they don't exist yet. Safe to
    call on every startup — every statement is CREATE ... IF NOT EXISTS."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8").replace(
        "__EMBEDDING_DIM__", str(settings.EMBEDDING_DIM)
    )
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# FastAPI dependency
def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

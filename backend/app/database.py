"""
SQLite connection management.

One physical file (see Settings.DB_PATH) holds both the relational tables
and the sqlite-vec virtual tables — "no separate vector database is needed"
per the PRD's stack section. Every connection loads the sqlite-vec
extension so `MATCH` queries against the vec0 tables work.

Two-phase schema: `init_db()` eagerly creates the core relational tables
(documents/pages/queries) at every app startup, same as before. The four
vec0 vector tables are created *lazily* instead, by
`ensure_vector_schema()`, the first time a real embedding vector's
dimension is known — see that function's docstring for why eager creation
never worked for genuine dimension auto-detection.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import sqlite_vec

from app.config import settings

CORE_SCHEMA_PATH = Path(__file__).parent / "db" / "schema_core.sql"
VECTOR_SCHEMA_PATH = Path(__file__).parent / "db" / "schema_vectors.sql"


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
    # check_same_thread=False: FastAPI runs sync dependencies (like get_db) via
    # anyio's threadpool, so a connection opened on thread A and closed on thread
    # B would raise sqlite3.ProgrammingError. This relaxes SQLite's thread affinity.
    conn = sqlite3.connect(path, check_same_thread=False)
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
    """Create the core relational tables (documents/pages/queries) if they
    don't exist yet. Safe to call on every startup — every statement is
    CREATE ... IF NOT EXISTS. Does NOT create the vec0 vector tables —
    see `ensure_vector_schema()`."""
    schema_sql = CORE_SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def ensure_vector_schema(conn: sqlite3.Connection, dim: int) -> None:
    """Idempotently create the four vec0 tables, sized to `dim`, if they
    don't already exist yet on this DB file. Called automatically by
    `vector_store.upsert_vector()` before every insert — see that
    function's docstring for why upsert is the right trigger point (it's
    the one place that always has a just-produced real vector in hand,
    and therefore its true length).

    Uses individual `conn.execute()` calls, one per statement, rather
    than `conn.executescript()`: `executescript()` issues an implicit
    COMMIT before running, which would prematurely commit whatever the
    *caller's* surrounding transaction was doing (e.g.
    `_process_single_page`'s page-row UPDATE, still uncommitted at the
    point it calls `upsert_vector`) — breaking this pipeline's
    atomic-page-checkpoint guarantee (see app/pipeline/tasks.py's module
    docstring).

    Plain `execute()` alone is *not* enough, though — this needed two
    rounds to get right, and the first round was wrong in a way worth
    recording. Python's `sqlite3` module's legacy implicit-transaction
    handling only opens a transaction automatically before
    INSERT/UPDATE/DELETE/REPLACE, never before a bare DDL statement like
    CREATE. So if `ensure_vector_schema()` happens to be the *first*
    statement run on a connection since its last commit (true here: it
    runs before `upsert_vector`'s own INSERT, which is exactly the
    common case for the very first embedding written to a fresh DB), the
    CREATE VIRTUAL TABLE statements execute in autocommit mode and are
    permanent immediately — a subsequent `conn.rollback()` would *not*
    undo them, silently breaking the atomicity this function's docstring
    used to (incorrectly) claim. Fixed below by explicitly opening a
    transaction first if one isn't already open, so the CREATE
    statements always join a transaction that a later `rollback()` can
    actually undo — verified with a dedicated test
    (test_upsert_inside_a_rolled_back_transaction_undoes_schema_creation_too
    in tests/test_retrieval_service.py) that a mid-transaction vec0
    CREATE followed by a rollback now correctly undoes the table
    creation along with everything else in that transaction, including
    when the CREATE is the very first statement in the block.

    Because vec0 columns are fixed-width at CREATE TABLE time, `dim` here
    is simply whatever the *first* successful embedding call in this DB
    file's lifetime happened to produce — once created, all four tables
    are permanent at that width for that DB file (CREATE ... IF NOT
    EXISTS is a no-op on an existing table). Switching to a
    differently-sized embedding model still always requires wiping
    storage/*.sqlite3* and re-ingesting — true before this migration and
    still true now; only *when* the width gets locked in has changed
    (first real embedding, not first app startup).

    All four tables are created together, from whichever one of them is
    touched first — they always come from the same embedding provider
    (one dimension for content/summary/keywords/document vectors alike),
    so there's no reason to stagger their creation independently.
    """
    if not conn.in_transaction:
        conn.execute("BEGIN")

    template = VECTOR_SCHEMA_PATH.read_text(encoding="utf-8")
    for statement in template.replace("__EMBEDDING_DIM__", str(dim)).split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)


def get_db() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

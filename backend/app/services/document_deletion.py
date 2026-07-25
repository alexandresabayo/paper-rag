"""
Document deletion (ISSUE-023, AGENT_TASKS.md).

Deleting a document needs to clean up four things, not just the
`documents` row:

1. The `documents` row itself — `pages` cascades automatically
   (`pages.document_id REFERENCES documents(id) ON DELETE CASCADE`,
   schema_core.sql, with `PRAGMA foreign_keys = ON` set on every
   connection — see database.py's `_configure`), so nothing extra is
   needed for the relational side.
2. Each deleted page's rowid in `page_content_vec` / `page_summary_vec` /
   `page_keywords_vec` — vec0 tables reuse `pages.rowid` directly rather
   than having their own identity (see vector_store.py's module
   docstring), so a plain `DELETE FROM pages` does NOT touch these — the
   vectors would become permanently orphaned rows with no page left to
   join back to, and no key any query would ever ask for again.
3. The document's own row in `document_vec`, keyed off `documents.rowid`
   the same way.
4. The stored PDF file on disk (`documents.file_path`).

Order matters: steps 2-3 need `pages`/`documents` to still exist so their
rowids can be looked up, so the vector deletes happen *before* the
`documents` row is deleted (whose cascade would otherwise pull the pages
out from under step 2). Step 4 is deliberately left to the caller, after
the DB transaction has committed — see `delete_document`'s docstring.
"""

from __future__ import annotations

import sqlite3

from app.models import documents as documents_repo
from app.services import vector_store

_PAGE_VECTOR_TABLES = ("page_content_vec", "page_summary_vec", "page_keywords_vec")


def delete_document(conn: sqlite3.Connection, document_id: str) -> str:
    """Deletes `document_id`'s row (cascading to its pages) and every
    vector row that referenced it, all within the caller's own
    transaction (see `app.database.session`/`get_db` — this function
    never commits or rolls back itself).

    Returns the document's `file_path` so the caller can unlink the PDF
    from disk *after* that transaction has actually committed. This
    function deliberately never touches the filesystem itself: a
    filesystem delete can't be rolled back the way a DB statement can,
    so doing it here — before the caller's commit is guaranteed to
    succeed — could leave the DB still referencing a file that's
    already gone if something downstream failed and rolled back.

    Raises `KeyError` if no document with this id exists, matching the
    convention `get_document_rowid`/`get_page_rowid` already use in
    `app.models.documents`.
    """
    doc = documents_repo.get_document(conn, document_id)
    if doc is None:
        raise KeyError(f"No document with id {document_id!r}")

    page_rowids = [
        documents_repo.get_page_rowid(conn, page["id"]) for page in documents_repo.list_pages(conn, document_id)
    ]
    document_rowid = documents_repo.get_document_rowid(conn, document_id)

    for page_rowid in page_rowids:
        for table in _PAGE_VECTOR_TABLES:
            vector_store.delete_vector(conn, table, page_rowid)
    vector_store.delete_vector(conn, "document_vec", document_rowid)

    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))

    return doc["file_path"]

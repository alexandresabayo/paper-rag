from __future__ import annotations

import io

"""
ISSUE-023 (AGENT_TASKS.md): `DELETE /api/ingestion/documents/{id}` must
clean up more than just the `documents` row - see
app/services/document_deletion.py's module docstring for the four
things a delete has to touch (the row itself, the three per-page vec0
tables, `document_vec`, and the stored PDF file on disk).
"""


def _upload(client, sample_pdf_bytes, filename="paper.pdf"):
    response = client.post(
        "/api/ingestion/documents",
        files={"files": (filename, io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200
    return response.json()[0]["document"]["id"]


def test_delete_removes_document_from_listing(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes)

    response = client.delete(f"/api/ingestion/documents/{doc_id}")
    assert response.status_code == 204
    assert response.content == b""

    listing = client.get("/api/ingestion/documents").json()
    assert not any(d["id"] == doc_id for d in listing)

    detail = client.get(f"/api/ingestion/documents/{doc_id}")
    assert detail.status_code == 404


def test_delete_removes_pages_via_cascade(tmp_workspace, client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes)

    client.delete(f"/api/ingestion/documents/{doc_id}")

    from app.database import get_connection

    conn = get_connection()
    remaining_pages = conn.execute("SELECT COUNT(*) AS n FROM pages WHERE document_id = ?", (doc_id,)).fetchone()
    assert remaining_pages["n"] == 0
    conn.close()


def test_delete_removes_page_and_document_vectors(tmp_workspace, client, sample_pdf_bytes):
    """Every vector row this document's pages/summaries/keywords were
    ever written into must be gone too - not just orphaned rowids with
    no page/document left to join back to."""
    from app.database import get_connection
    from app.services import vector_store

    doc_id = _upload(client, sample_pdf_bytes)

    conn = get_connection()
    # Fully processed (MOCK_MODE) 2-page doc: content, summary, and
    # keyword vectors for both pages, plus one document-level vector.
    assert vector_store.table_row_count(conn, "page_content_vec") == 2
    assert vector_store.table_row_count(conn, "page_summary_vec") == 2
    assert vector_store.table_row_count(conn, "page_keywords_vec") == 2
    assert vector_store.table_row_count(conn, "document_vec") == 1
    conn.close()

    response = client.delete(f"/api/ingestion/documents/{doc_id}")
    assert response.status_code == 204

    conn = get_connection()
    assert vector_store.table_row_count(conn, "page_content_vec") == 0
    assert vector_store.table_row_count(conn, "page_summary_vec") == 0
    assert vector_store.table_row_count(conn, "page_keywords_vec") == 0
    assert vector_store.table_row_count(conn, "document_vec") == 0
    conn.close()


def test_delete_removes_pdf_file_from_disk(client, sample_pdf_bytes):
    from app.config import settings

    doc_id = _upload(client, sample_pdf_bytes)
    pdf_path = settings.PDF_STORAGE_DIR / f"{doc_id}.pdf"
    assert pdf_path.exists()

    client.delete(f"/api/ingestion/documents/{doc_id}")

    assert not pdf_path.exists()


def test_delete_404_for_unknown_document(client):
    response = client.delete("/api/ingestion/documents/does-not-exist")
    assert response.status_code == 404


def test_delete_leaves_other_documents_and_their_vectors_untouched(client, sample_pdf_bytes):
    """A multi-document corpus: deleting one document must not disturb
    another document's rows or vectors."""
    from app.database import get_connection
    from app.services import vector_store

    doc_id_1 = _upload(client, sample_pdf_bytes, filename="one.pdf")
    # A second, distinct document (different bytes -> different content-
    # addressed id) so it isn't deduped against the first.
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "A completely different second document for the deletion isolation test.")
    other_bytes = doc.tobytes()
    doc.close()
    doc_id_2 = _upload(client, other_bytes, filename="two.pdf")
    assert doc_id_1 != doc_id_2

    client.delete(f"/api/ingestion/documents/{doc_id_1}")

    listing = client.get("/api/ingestion/documents").json()
    assert not any(d["id"] == doc_id_1 for d in listing)
    assert any(d["id"] == doc_id_2 for d in listing)

    conn = get_connection()
    assert vector_store.table_row_count(conn, "document_vec") == 1
    conn.close()


def test_reuploading_after_delete_creates_a_fresh_document(client, sample_pdf_bytes):
    """The content-addressed id is stable, but once the row is deleted
    there's nothing left to dedupe against - re-uploading the exact
    same bytes must start ingestion again from scratch, not silently
    no-op the way a re-upload of a still-existing document does."""
    doc_id = _upload(client, sample_pdf_bytes)
    client.delete(f"/api/ingestion/documents/{doc_id}")

    second = _upload(client, sample_pdf_bytes)
    assert second == doc_id  # same content-addressed id

    detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
    assert detail["status"] == "done"
    assert detail["total_pages"] == 2

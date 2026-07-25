from __future__ import annotations

import io

"""
ISSUE-022 (AGENT_TASKS.md): `POST /api/ingestion/documents/retry-all`
re-enqueues every currently-failed document in one call, using the same
per-document resume-from-checkpoint mechanism as the existing
single-document retry endpoint (`POST /documents/{id}/retry`) - see
that endpoint's docstring in app/routers/ingestion.py.

Failures below are keyed off the target document's own content-
addressed id (computed up front via `compute_document_id`), not its
upload filename - `_extract_page_text` only ever sees
`storage/pdfs/<hash>.pdf`, never the original filename, so a filename-
based monkeypatch would silently fail to distinguish documents.
"""


def _upload(client, content: bytes, filename: str):
    response = client.post(
        "/api/ingestion/documents",
        files={"files": (filename, io.BytesIO(content), "application/pdf")},
    )
    assert response.status_code == 200
    return response.json()[0]["document"]["id"]


def _make_pdf_bytes(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_retry_all_is_a_noop_when_nothing_failed(client, sample_pdf_bytes):
    _upload(client, sample_pdf_bytes, "ok.pdf")

    response = client.post("/api/ingestion/documents/retry-all")
    assert response.status_code == 200
    assert response.json() == []

    # And the healthy document is untouched.
    listing = client.get("/api/ingestion/documents").json()
    assert listing[0]["status"] == "done"


def test_retry_all_is_a_noop_on_an_empty_corpus(client):
    response = client.post("/api/ingestion/documents/retry-all")
    assert response.status_code == 200
    assert response.json() == []


def test_retry_all_only_retries_failed_documents(client, sample_pdf_bytes, monkeypatch):
    """Two documents: one that ingests cleanly, one that's made to fail
    permanently (rather than transiently) so it stays 'failed' and is a
    genuine retry-all target. Only the failed one should be retried."""
    import app.pipeline.tasks as tasks_module
    from app.utils.hashing import compute_document_id

    original_extract = tasks_module._extract_page_text

    broken_bytes = _make_pdf_bytes("A document whose ingestion will be made to fail for this test.")
    broken_id = compute_document_id(broken_bytes)

    def fail_only_for_broken_doc(pdf_path, page_number):
        if broken_id in str(pdf_path):
            raise RuntimeError("simulated permanent failure")
        return original_extract(pdf_path, page_number)

    monkeypatch.setattr(tasks_module, "_extract_page_text", fail_only_for_broken_doc)

    healthy_id = _upload(client, sample_pdf_bytes, "healthy.pdf")
    broken_upload_id = _upload(client, broken_bytes, "broken.pdf")
    assert broken_upload_id == broken_id

    healthy_detail = client.get(f"/api/ingestion/documents/{healthy_id}").json()
    assert healthy_detail["status"] == "done"
    broken_detail = client.get(f"/api/ingestion/documents/{broken_id}").json()
    assert broken_detail["status"] == "failed"

    monkeypatch.setattr(tasks_module, "_extract_page_text", original_extract)  # "fix" it before retrying

    response = client.post("/api/ingestion/documents/retry-all")
    assert response.status_code == 200
    body = response.json()
    assert [d["id"] for d in body] == [broken_id]
    assert body[0]["status"] == "done"

    healthy_after = client.get(f"/api/ingestion/documents/{healthy_id}").json()
    assert healthy_after["status"] == "done"
    broken_after = client.get(f"/api/ingestion/documents/{broken_id}").json()
    assert broken_after["status"] == "done"


def test_retry_all_retries_multiple_failed_documents(client, monkeypatch):
    import app.pipeline.tasks as tasks_module

    def always_fail(pdf_path, page_number):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(tasks_module, "_extract_page_text", always_fail)

    id_a = _upload(client, _make_pdf_bytes("First broken document for the multi-retry test."), "a.pdf")
    id_b = _upload(client, _make_pdf_bytes("Second broken document for the multi-retry test."), "b.pdf")

    for doc_id in (id_a, id_b):
        detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
        assert detail["status"] == "failed"

    monkeypatch.undo()  # restore the real _extract_page_text before retrying

    response = client.post("/api/ingestion/documents/retry-all")
    retried_ids = {d["id"] for d in response.json()}
    assert retried_ids == {id_a, id_b}
    assert all(d["status"] == "done" for d in response.json())

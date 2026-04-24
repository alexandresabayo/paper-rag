from __future__ import annotations

import io


def _upload(client, sample_pdf_bytes, filename="paper.pdf"):
    return client.post(
        "/api/ingestion/documents",
        files={"files": (filename, io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )


def test_upload_processes_synchronously_in_mock_mode(client, sample_pdf_bytes):
    response = _upload(client, sample_pdf_bytes)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    doc = body[0]["document"]
    assert body[0]["enqueued"] is True
    assert doc["total_pages"] == 2
    assert doc["status"] == "done"
    assert doc["pages_done"] == 2
    assert doc["pages_failed"] == 0
    # DevShimVLMProvider reports 'vlm' success in MOCK_MODE - see ocr_service.py
    assert doc["metadata_status"] in ("done", "na")


def test_reupload_same_bytes_is_a_noop(client, sample_pdf_bytes):
    first = _upload(client, sample_pdf_bytes).json()[0]
    second = _upload(client, sample_pdf_bytes, filename="same-paper-again.pdf").json()[0]
    assert first["document"]["id"] == second["document"]["id"]
    assert second["enqueued"] is False  # already done, re-upload doesn't re-trigger


def test_list_and_detail(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes).json()[0]["document"]["id"]

    listing = client.get("/api/ingestion/documents")
    assert listing.status_code == 200
    assert any(d["id"] == doc_id for d in listing.json())

    detail = client.get(f"/api/ingestion/documents/{doc_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["pages"]) == 2
    assert all(p["processing_status"] == "done" for p in body["pages"])
    assert all(p["has_summary"] for p in body["pages"])  # long enough to skip the short-page path


def test_detail_404_for_unknown_document(client):
    response = client.get("/api/ingestion/documents/does-not-exist")
    assert response.status_code == 404


def test_retry_endpoint_reprocesses(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes).json()[0]["document"]["id"]
    response = client.post(f"/api/ingestion/documents/{doc_id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] == "done"


def test_manual_metadata_edit(client, sample_pdf_bytes):
    doc_id = _upload(client, sample_pdf_bytes).json()[0]["document"]["id"]

    response = client.patch(
        f"/api/ingestion/documents/{doc_id}/metadata",
        json={"title": "A Corrected Title", "authors": ["A. Researcher"], "year": "2024"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "A Corrected Title"
    assert body["authors"] == ["A. Researcher"]
    assert body["metadata_edited_by_admin"] is True


def test_quality_report(client, sample_pdf_bytes):
    _upload(client, sample_pdf_bytes)
    response = client.get("/api/ingestion/reports/quality")
    assert response.status_code == 200
    body = response.json()
    assert body["documents"]["total_documents"] == 1
    assert body["pages"]["total_pages"] == 2


def test_rejects_non_pdf(client):
    response = client.post(
        "/api/ingestion/documents",
        files={"files": ("not-a-pdf.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400

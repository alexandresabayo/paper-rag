from __future__ import annotations

import io


def test_page_failure_halts_document_and_retry_resumes(client, sample_pdf_bytes, monkeypatch):
    import app.pipeline.tasks as tasks_module

    original_extract = tasks_module._extract_page_text
    fail_toggle = {"active": True}

    def flaky_extract(pdf_path, page_number):
        if page_number == 2 and fail_toggle["active"]:
            raise RuntimeError("simulated failure on page 2")
        return original_extract(pdf_path, page_number)

    monkeypatch.setattr(tasks_module, "_extract_page_text", flaky_extract)

    upload_response = client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert upload_response.status_code == 200
    doc_id = upload_response.json()[0]["document"]["id"]

    detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
    assert detail["status"] == "failed"
    assert detail["last_error"] and "simulated failure" in detail["last_error"]
    pages_by_number = {p["page_number"]: p for p in detail["pages"]}
    assert pages_by_number[1]["processing_status"] == "done"
    assert pages_by_number[2]["processing_status"] == "failed"
    assert "simulated failure" in pages_by_number[2]["error_message"]

    # Fix whatever was "wrong" and retry - should resume from page 2, not
    # restart from page 1.
    fail_toggle["active"] = False
    retry_response = client.post(f"/api/ingestion/documents/{doc_id}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "done"

    detail_after = client.get(f"/api/ingestion/documents/{doc_id}").json()
    assert detail_after["status"] == "done"
    assert all(p["processing_status"] == "done" for p in detail_after["pages"])


def test_resume_page_number_helper(client, tmp_workspace):
    from app.database import session
    from app.models import documents as documents_repo

    with session() as conn:
        documents_repo.create_document(
            conn, document_id="doc-1", file_name="x.pdf", file_path="/tmp/x.pdf", total_pages=3
        )
        documents_repo.create_pages(conn, document_id="doc-1", total_pages=3)

    with session() as conn:
        # Nothing done yet -> resume from page 1.
        assert documents_repo.get_resume_page_number(conn, "doc-1") == 1

        documents_repo.update_page_fields(conn, "doc-1:00001", processing_status="done")

    with session() as conn:
        # Page 1 done -> resume from page 2.
        assert documents_repo.get_resume_page_number(conn, "doc-1") == 2

        documents_repo.update_page_fields(conn, "doc-1:00002", processing_status="done")
        documents_repo.update_page_fields(conn, "doc-1:00003", processing_status="done")

    with session() as conn:
        # Everything done -> no resume point.
        assert documents_repo.get_resume_page_number(conn, "doc-1") is None

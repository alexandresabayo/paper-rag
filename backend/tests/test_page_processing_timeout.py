from __future__ import annotations

import io
import time

import pytest

"""
ISSUE-014 (AGENT_TASKS.md): a per-page processing timeout, so a hung
model call fails that step (retryable) instead of hanging the
single-worker queue indefinitely. See `_run_with_timeout`'s docstring in
app/pipeline/tasks.py.
"""


# ---------------------------------------------------------------------
# _run_with_timeout in isolation - fast, deterministic, no HTTP/pipeline
# involved at all.
# ---------------------------------------------------------------------


def test_run_with_timeout_passes_through_fast_call():
    from app.pipeline.tasks import _run_with_timeout

    assert _run_with_timeout(lambda x, y: x + y, 20, 22, timeout_seconds=5) == 42


def test_run_with_timeout_raises_timeout_error_on_a_slow_call():
    from app.pipeline.tasks import PageProcessingTimeoutError, _run_with_timeout

    def slow():
        time.sleep(0.5)
        return "too late"

    with pytest.raises(PageProcessingTimeoutError):
        _run_with_timeout(slow, timeout_seconds=0.05)


def test_run_with_timeout_propagates_the_original_exception_unchanged():
    """A real failure (not a timeout) must surface as itself, not get
    wrapped into PageProcessingTimeoutError - callers like
    `_extract_page_text` depend on catching the *original* exception
    type (e.g. OCRExtractionError) to decide what to do next."""
    from app.pipeline.tasks import _run_with_timeout

    class CustomError(RuntimeError):
        pass

    def boom():
        raise CustomError("kaboom")

    with pytest.raises(CustomError, match="kaboom"):
        _run_with_timeout(boom, timeout_seconds=5)


# ---------------------------------------------------------------------
# Through the real pipeline - confirms a hang at each of the wrapped call
# sites degrades to a retryable failure rather than hanging the request.
# ---------------------------------------------------------------------


def test_hung_page_summary_call_fails_the_page_and_is_retryable(client, sample_pdf_bytes, monkeypatch):
    import app.pipeline.tasks as tasks_module
    from app.config import settings

    monkeypatch.setattr(settings, "PAGE_PROCESSING_TIMEOUT_SECONDS", 0.2)

    original_run_prompt = tasks_module.run_prompt

    def hanging_on_page_summary(name, **kwargs):
        if name == "ingestion/page_summary":
            time.sleep(1.0)  # well past the 0.2s timeout above
        return original_run_prompt(name, **kwargs)

    monkeypatch.setattr(tasks_module, "run_prompt", hanging_on_page_summary)

    upload_response = client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    doc_id = upload_response.json()[0]["document"]["id"]

    detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
    assert detail["status"] == "failed"
    failed_pages = [p for p in detail["pages"] if p["processing_status"] == "failed"]
    assert failed_pages, "expected at least one page to be marked failed, not left hanging/pending"
    assert "exceeded" in failed_pages[0]["error_message"].lower()
    assert "0.2" in failed_pages[0]["error_message"]

    # "Fix" the hang and retry - should resume and succeed, proving the
    # failure is a normal, retryable one, not a permanent wedge.
    monkeypatch.setattr(tasks_module, "run_prompt", original_run_prompt)
    retry_response = client.post(f"/api/ingestion/documents/{doc_id}/retry")
    assert retry_response.status_code == 200
    assert retry_response.json()["status"] == "done"


def test_hung_extraction_call_fails_the_page_and_is_retryable(client, sample_pdf_bytes, monkeypatch):
    """Same guarantee, but for the OCR extraction step itself rather than
    the summary/keywords step."""
    import app.pipeline.tasks as tasks_module
    from app.config import settings

    monkeypatch.setattr(settings, "PAGE_PROCESSING_TIMEOUT_SECONDS", 0.2)

    original_get_primary = tasks_module.get_primary_ocr_provider

    class HangingPrimary:
        def extract_page(self, pdf_path, page_number):
            time.sleep(1.0)

    monkeypatch.setattr(tasks_module, "get_primary_ocr_provider", lambda: HangingPrimary())

    upload_response = client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    doc_id = upload_response.json()[0]["document"]["id"]

    detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
    assert detail["status"] == "failed"
    failed_pages = [p for p in detail["pages"] if p["processing_status"] == "failed"]
    assert failed_pages
    assert "exceeded" in failed_pages[0]["error_message"].lower()

    monkeypatch.setattr(tasks_module, "get_primary_ocr_provider", original_get_primary)
    retry_response = client.post(f"/api/ingestion/documents/{doc_id}/retry")
    assert retry_response.json()["status"] == "done"


def test_timeout_is_configurable_and_generous_by_default(client, sample_pdf_bytes):
    """Regression guard: the default 300s timeout doesn't interfere with
    normal (fast, mocked) ingestion."""
    response = client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()[0]["document"]["status"] == "done"

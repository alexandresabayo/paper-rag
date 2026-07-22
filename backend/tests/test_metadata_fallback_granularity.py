from __future__ import annotations

import io

"""
ISSUE-007 (AGENT_TASKS.md): the metadata-extraction fallback rule needs to
be gated on which *extractor* produced the source pages' text, not merely
on whether that text happens to be non-empty. See the docstring added at
the relevant check in app/pipeline/tasks.py::_maybe_extract_metadata.
"""


def _upload(client, sample_pdf_bytes):
    response = client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200
    return response.json()[0]["document"]["id"]


def test_metadata_stays_na_when_source_pages_used_fallback_extractor(client, sample_pdf_bytes, monkeypatch):
    """If any of the first METADATA_SOURCE_PAGE_COUNT pages had to fall
    back to pypdf (VLM failed), metadata extraction must not run against
    that degraded text - metadata_status should land on 'na', the same as
    already happens for a page's own summary/keywords."""
    import app.pipeline.tasks as tasks_module
    from app.services.ocr_service import OCRExtractionError

    class AlwaysFailPrimary:
        def extract_page(self, pdf_path, page_number):
            raise OCRExtractionError("simulated VLM outage")

    monkeypatch.setattr(tasks_module, "get_primary_ocr_provider", lambda: AlwaysFailPrimary())

    doc_id = _upload(client, sample_pdf_bytes)

    detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
    assert detail["status"] == "done"
    # Every page fell back - real pypdf text, but no VLM path.
    assert detail["pages"], "expected pages in the detail response"
    assert all(p["extractor_used"] == "fallback" for p in detail["pages"])

    # ... yet metadata must not have been attempted from that degraded text.
    assert detail["metadata_status"] == "na"
    assert detail["title"] is None
    assert detail["authors"] is None
    assert detail["doc_type"] is None

    # The existing per-page rule (summary/keywords require extractor_used
    # == "vlm") should hold too - this test is really checking that
    # metadata now follows the *same* rule, not a looser one.
    assert all(not p["has_summary"] for p in detail["pages"])
    assert all(not p["has_keywords"] for p in detail["pages"])


def test_metadata_extracted_when_all_source_pages_used_vlm(client, sample_pdf_bytes):
    """Regression guard for the opposite branch: MOCK_MODE's
    DevShimVLMProvider reports every page as 'vlm', so metadata
    extraction should still run normally."""
    doc_id = _upload(client, sample_pdf_bytes)
    detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
    assert all(p["extractor_used"] == "vlm" for p in detail["pages"])
    assert detail["metadata_status"] == "done"


def test_metadata_stays_na_when_only_some_source_pages_used_fallback(client, sample_pdf_bytes, monkeypatch):
    """Mixed case: page 1 succeeds via VLM, page 2 falls back. Since both
    pages are within METADATA_SOURCE_PAGE_COUNT for this 2-page fixture,
    a single fallback page among the source pages is enough to withhold
    metadata - PRD 2.A #2 extracts metadata "from the first 2-3 pages
    combined", treating them as one unit, so a partially-degraded unit is
    still a degraded unit."""
    import app.pipeline.tasks as tasks_module
    from app.services.ocr_service import OCRExtractionError, PyPDFFallbackProvider

    class FlakyPrimary:
        def __init__(self):
            self._fallback = PyPDFFallbackProvider()

        def extract_page(self, pdf_path, page_number):
            if page_number == 2:
                raise OCRExtractionError("simulated VLM outage on page 2")
            # Page 1 "succeeds" via VLM (shimmed with real pypdf text, same
            # as DevShimVLMProvider does elsewhere in MOCK_MODE).
            return self._fallback.extract_page(pdf_path, page_number)

    monkeypatch.setattr(tasks_module, "get_primary_ocr_provider", lambda: FlakyPrimary())

    doc_id = _upload(client, sample_pdf_bytes)
    detail = client.get(f"/api/ingestion/documents/{doc_id}").json()
    pages_by_number = {p["page_number"]: p for p in detail["pages"]}
    assert pages_by_number[1]["extractor_used"] == "vlm"
    assert pages_by_number[2]["extractor_used"] == "fallback"

    assert detail["metadata_status"] == "na"
    assert detail["title"] is None

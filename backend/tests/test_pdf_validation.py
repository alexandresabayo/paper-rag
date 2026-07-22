from __future__ import annotations

import io

"""
ISSUE-010 / ISSUE-011 (AGENT_TASKS.md): upload-time PDF validation and
size/page limits. Every fixture PDF here is a real, structurally valid
(or deliberately invalid) PDF built with fitz/pypdf at test time - not a
hand-waved stand-in - so these tests exercise the actual PyMuPDF/pypdf
behavior the implementation was verified against (see
app/services/pdf_render.py's PDFCorruptedError/PDFEncryptedError/
PDFEmptyError docstrings).
"""


def _upload(client, filename: str, content: bytes, content_type: str = "application/pdf"):
    return client.post(
        "/api/ingestion/documents",
        files={"files": (filename, io.BytesIO(content), content_type)},
    )


def _make_zero_page_pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_encrypted_pdf_bytes() -> bytes:
    import fitz

    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    buf = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret123", owner_pw="ownersecret")
    doc.close()
    return buf


# ---------------------------------------------------------------------
# ISSUE-010: corrupted / encrypted / zero-page PDFs
# ---------------------------------------------------------------------


def test_rejects_garbage_bytes_named_like_a_pdf(client):
    """A file that merely has a .pdf extension/content-type without
    being one at all - previously an unhandled 500 (fitz.FileDataError
    propagating uncaught), not a clean 4xx."""
    response = _upload(client, "definitely-not-a-pdf.pdf", b"this is not a pdf, just plain text bytes")
    assert response.status_code == 400
    assert "could not be parsed as a pdf" in response.json()["detail"].lower()


def test_rejects_encrypted_pdf(client):
    response = _upload(client, "encrypted.pdf", _make_encrypted_pdf_bytes())
    assert response.status_code == 400
    assert "password-protected" in response.json()["detail"].lower()


def test_rejects_zero_page_pdf(client):
    response = _upload(client, "empty.pdf", _make_zero_page_pdf_bytes())
    assert response.status_code == 400
    assert "zero pages" in response.json()["detail"].lower()


def test_rejected_files_are_never_written_to_storage(client, tmp_workspace):
    """Validation must happen entirely from bytes, before any disk write
    or DB row - a rejected file should leave no trace."""
    from app.config import settings

    before = list(settings.PDF_STORAGE_DIR.glob("*.pdf"))
    response = _upload(client, "encrypted.pdf", _make_encrypted_pdf_bytes())
    assert response.status_code == 400

    after = list(settings.PDF_STORAGE_DIR.glob("*.pdf"))
    assert before == after

    listing = client.get("/api/ingestion/documents")
    assert listing.json() == []


def test_still_rejects_non_pdf_content_type_and_extension(client):
    """Regression guard: the pre-existing extension/content-type check
    (unrelated to the new structural validation) still works."""
    response = _upload(client, "not-a-pdf.txt", b"hello", content_type="text/plain")
    assert response.status_code == 400


def test_valid_pdf_still_uploads_successfully(client, sample_pdf_bytes):
    """Regression guard: a normal, valid PDF isn't caught by any of the
    new checks."""
    response = _upload(client, "paper.pdf", sample_pdf_bytes)
    assert response.status_code == 200
    assert response.json()[0]["document"]["total_pages"] == 2


# ---------------------------------------------------------------------
# ISSUE-011: upload size / page-count limits
# ---------------------------------------------------------------------


def test_rejects_file_exceeding_max_size(client, monkeypatch, sample_pdf_bytes):
    from app.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_FILE_SIZE_BYTES", 10)  # smaller than any real PDF

    response = _upload(client, "paper.pdf", sample_pdf_bytes)
    assert response.status_code == 400
    assert "byte limit" in response.json()["detail"].lower() or "exceeding" in response.json()["detail"].lower()


def test_rejects_pdf_exceeding_max_page_count(client, monkeypatch, sample_pdf_bytes):
    from app.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_PAGE_COUNT", 1)  # sample fixture has 2 pages

    response = _upload(client, "paper.pdf", sample_pdf_bytes)
    assert response.status_code == 400
    assert "page limit" in response.json()["detail"].lower() or "exceeding" in response.json()["detail"].lower()


def test_size_and_page_limits_are_configurable_and_permissive_by_default(client, sample_pdf_bytes):
    """Regression guard: default limits (100MB / 1000 pages) don't
    interfere with the small test fixture."""
    response = _upload(client, "paper.pdf", sample_pdf_bytes)
    assert response.status_code == 200

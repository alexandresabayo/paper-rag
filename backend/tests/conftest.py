from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import fitz
import pytest


@pytest.fixture()
def tmp_workspace(monkeypatch):
    """Point every storage path at a fresh temp dir for the duration of a
    test, and force MOCK_MODE on regardless of the environment's .env."""
    workdir = Path(tempfile.mkdtemp(prefix="paper_rag_test_"))
    monkeypatch.setenv("DB_PATH", str(workdir / "test.sqlite3"))
    monkeypatch.setenv("HUEY_DB_PATH", str(workdir / "huey.sqlite3"))
    monkeypatch.setenv("PDF_STORAGE_DIR", str(workdir / "pdfs"))
    monkeypatch.setenv("MOCK_MODE", "true")

    # Settings is a module-level singleton constructed at import time, and
    # several other modules read `settings.DB_PATH` at *call* time (not
    # import time) via `from app.config import settings`, so re-pointing
    # its fields directly (rather than re-importing) is what actually
    # takes effect everywhere.
    from app.config import settings

    settings.DB_PATH = workdir / "test.sqlite3"
    settings.HUEY_DB_PATH = workdir / "huey.sqlite3"
    settings.PDF_STORAGE_DIR = workdir / "pdfs"
    settings.MOCK_MODE = True
    settings.PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    from app.database import init_db

    init_db()

    yield workdir

    shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture()
def sample_pdf_bytes() -> bytes:
    """A small, real, in-memory 2-page PDF (not a fixture file on disk) so
    tests don't depend on any external asset."""
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            f"Page {i + 1}. This is a short synthetic test document used only "
            "by the automated test suite. It exists purely to exercise the "
            "ingestion pipeline end to end without a real scientific PDF. "
            "It has enough sentences to avoid the short-page special case. "
            "Nothing about its content is meaningful.",
        )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture()
def client(tmp_workspace):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

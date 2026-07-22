"""
Ingestion ("pipeline dashboard") router — PRD Section 6:

    "Pipeline dashboard supports manual intervention, not just monitoring"
    (a) manually retry a failed document — resumes from checkpoint
    (b) edit/correct LLM-extracted metadata by hand
    (c) upload new PDFs directly to kick off ingestion

Single-admin, no auth for v1 (Section 6) — there is deliberately no
authentication/authorization here. Add it if/when a second operator needs
access; see AGENT_TASKS.md.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.database import get_db, session
from app.models import documents as documents_repo
from app.pipeline.tasks import ingest_document_task
from app.schemas.ingestion import (
    DocumentDetail,
    DocumentMetadataUpdate,
    DocumentSummary,
    PageStatus,
    QualityReport,
    UploadResult,
)
from app.services import quality
from app.services.pdf_render import (
    PDFCorruptedError,
    PDFEmptyError,
    PDFEncryptedError,
    inspect_pdf_bytes,
)
from app.utils.hashing import compute_document_id

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


@router.post("/documents", response_model=list[UploadResult])
async def upload_documents(files: Annotated[list[UploadFile], File(...)]) -> list[UploadResult]:
    """(c) Upload new PDFs directly to kick off ingestion. Accepts one or
    more files in a single multipart request (batch upload, PRD 2.A #8).
    Each file becomes its own document + Huey task; re-uploading the exact
    same bytes is a no-op (content-addressed id, see hashing.py).

    Every file is fully validated (extension/content-type, size, PDF
    structure, page count - ISSUE-010/ISSUE-011, AGENT_TASKS.md) *before*
    anything is written to `PDF_STORAGE_DIR` or any DB row is created, so
    a rejected file never touches storage. As before, the first invalid
    file in a batch aborts the whole request (consistent with the
    pre-existing non-PDF check below, not a new inconsistency introduced
    here) rather than silently skipping it or returning a partial-success
    shape the API didn't previously support.
    """
    from app.config import settings

    results: list[UploadResult] = []

    for upload in files:
        if upload.content_type not in ("application/pdf", "application/x-pdf") and not (
            upload.filename or ""
        ).lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{upload.filename!r} is not a PDF")

        file_bytes = await upload.read()

        if len(file_bytes) > settings.MAX_UPLOAD_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{upload.filename!r} is {len(file_bytes):,} bytes, "
                    f"exceeding the {settings.MAX_UPLOAD_FILE_SIZE_BYTES:,}-byte limit"
                ),
            )

        try:
            total_pages = inspect_pdf_bytes(file_bytes)
        except PDFEncryptedError:
            raise HTTPException(
                status_code=400,
                detail=f"{upload.filename!r} is password-protected; encrypted PDFs are not supported",
            )
        except PDFEmptyError:
            raise HTTPException(status_code=400, detail=f"{upload.filename!r} has zero pages")
        except PDFCorruptedError as exc:
            raise HTTPException(
                status_code=400, detail=f"{upload.filename!r} could not be parsed as a PDF: {exc}"
            )

        if total_pages > settings.MAX_UPLOAD_PAGE_COUNT:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{upload.filename!r} has {total_pages:,} pages, "
                    f"exceeding the {settings.MAX_UPLOAD_PAGE_COUNT:,}-page limit"
                ),
            )

        document_id = compute_document_id(file_bytes)

        pdf_path = settings.PDF_STORAGE_DIR / f"{document_id}.pdf"
        already_existed = pdf_path.exists()
        if not already_existed:
            pdf_path.write_bytes(file_bytes)

        with session() as conn:
            documents_repo.create_document(
                conn,
                document_id=document_id,
                file_name=upload.filename or f"{document_id}.pdf",
                file_path=str(pdf_path),
                total_pages=total_pages,
            )
            documents_repo.create_pages(conn, document_id=document_id, total_pages=total_pages)
            pre_ingest_status = documents_repo.get_document(conn, document_id)["status"]

        enqueued = False
        if pre_ingest_status in ("pending", "failed"):
            ingest_document_task(document_id)
            enqueued = True

        with session() as conn:
            doc_row = next(r for r in documents_repo.list_documents(conn) if r["id"] == document_id)

        results.append(UploadResult(document=DocumentSummary.from_row(doc_row), enqueued=enqueued))

    return results


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(db: sqlite3.Connection = Depends(get_db)) -> list[DocumentSummary]:
    rows = documents_repo.list_documents(db)
    return [DocumentSummary.from_row(r) for r in rows]


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document_detail(document_id: str, db: sqlite3.Connection = Depends(get_db)) -> DocumentDetail:
    rows = documents_repo.list_documents(db)
    row = next((r for r in rows if r["id"] == document_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")

    pages = documents_repo.list_pages(db, document_id)
    summary = DocumentSummary.from_row(row)
    return DocumentDetail(
        **summary.model_dump(),
        running_summary=row.get("running_summary"),
        pages=[PageStatus.from_row(p) for p in pages],
    )


@router.post("/documents/{document_id}/retry", response_model=DocumentSummary)
def retry_document(document_id: str, db: sqlite3.Connection = Depends(get_db)) -> DocumentSummary:
    """(a) Manually retry a failed (or stuck) document. Resumes from the
    last successfully checkpointed page (2.A #12) — the task itself
    figures out the resume point; this endpoint just re-enqueues it."""
    doc = documents_repo.get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    ingest_document_task(document_id)

    rows = documents_repo.list_documents(db)
    row = next(r for r in rows if r["id"] == document_id)
    return DocumentSummary.from_row(row)


@router.patch("/documents/{document_id}/metadata", response_model=DocumentSummary)
def edit_metadata(
    document_id: str, update: DocumentMetadataUpdate, db: sqlite3.Connection = Depends(get_db)
) -> DocumentSummary:
    """(b) Edit/correct LLM-extracted metadata by hand."""
    doc = documents_repo.get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    fields = update.model_dump(exclude_unset=True)
    authors = fields.pop("authors", None)
    documents_repo.set_document_metadata(
        db,
        document_id,
        doc_type=fields.get("doc_type", doc.get("doc_type")),
        authors=authors if authors is not None else None,
        year=fields.get("year", doc.get("year")),
        title=fields.get("title", doc.get("title")),
        venue=fields.get("venue", doc.get("venue")),
        doi=fields.get("doi", doc.get("doi")),
        acronym=fields.get("acronym", doc.get("acronym")),
        metadata_status="done",
        edited_by_admin=True,
    )
    remaining = {k: v for k, v in fields.items() if k in ("language", "license", "source")}
    if remaining:
        documents_repo.update_document_fields(db, document_id, **remaining)
    db.commit()

    rows = documents_repo.list_documents(db)
    row = next(r for r in rows if r["id"] == document_id)
    return DocumentSummary.from_row(row)


@router.get("/reports/quality", response_model=QualityReport)
def get_quality_report(db: sqlite3.Connection = Depends(get_db)) -> QualityReport:
    return QualityReport(**quality.generate_quality_report(db))

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class PageStatus(BaseModel):
    page_number: int
    processing_status: Literal["pending", "done", "failed"]
    extractor_used: str | None = None
    is_short_page: bool = False
    has_summary: bool = False
    has_keywords: bool = False
    error_message: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "PageStatus":
        return cls(
            page_number=row["page_number"],
            processing_status=row["processing_status"],
            extractor_used=row.get("extractor_used"),
            is_short_page=bool(row.get("is_short_page")),
            has_summary=bool(row.get("page_summary")),
            has_keywords=bool(row.get("keywords_json")),
            error_message=row.get("error_message"),
        )


class DocumentSummary(BaseModel):
    id: str
    file_name: str
    total_pages: int
    pages_done: int
    pages_failed: int
    pages_used_fallback: int
    status: Literal["pending", "processing", "done", "failed"]
    metadata_status: Literal["pending", "done", "na"]
    doc_type: str | None = None
    title: str | None = None
    authors: list[str] | None = None
    year: str | None = None
    venue: str | None = None
    doi: str | None = None
    acronym: str | None = None
    language: str | None = None
    metadata_edited_by_admin: bool = False
    last_error: str | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "DocumentSummary":
        return cls(
            id=row["id"],
            file_name=row["file_name"],
            total_pages=row["total_pages"],
            pages_done=row.get("pages_done") or 0,
            pages_failed=row.get("pages_failed") or 0,
            pages_used_fallback=row.get("pages_used_fallback") or 0,
            status=row["status"],
            metadata_status=row["metadata_status"],
            doc_type=row.get("doc_type"),
            title=row.get("title"),
            authors=json.loads(row["authors_json"]) if row.get("authors_json") else None,
            year=row.get("year"),
            venue=row.get("venue"),
            doi=row.get("doi"),
            acronym=row.get("acronym"),
            language=row.get("language"),
            metadata_edited_by_admin=bool(row.get("metadata_edited_by_admin")),
            last_error=row.get("last_error"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class DocumentDetail(DocumentSummary):
    running_summary: str | None = None
    pages: list[PageStatus] = Field(default_factory=list)


class DocumentMetadataUpdate(BaseModel):
    """All fields optional - PATCH semantics (Section 6b manual correction)."""

    doc_type: str | None = None
    authors: list[str] | None = None
    year: str | None = None
    title: str | None = None
    venue: str | None = None
    doi: str | None = None
    acronym: str | None = None
    language: str | None = None
    license: str | None = None
    source: str | None = None


class UploadResult(BaseModel):
    document: DocumentSummary
    enqueued: bool


class QualityReport(BaseModel):
    documents: dict[str, Any]
    pages: dict[str, Any]
    failed_documents: list[dict[str, Any]]
    failed_pages: list[dict[str, Any]]
    na_metadata_documents: list[dict[str, Any]]

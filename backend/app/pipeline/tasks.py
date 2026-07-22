"""
Ingestion pipeline orchestration — PRD Section 2.A.

One Huey task per document (`ingest_document_task`); Huey itself is
configured as a single, strictly-FIFO worker (app/pipeline/huey_app.py), so
documents are processed one at a time and never contend for GPU VRAM.

The actual work is in plain functions below (`run_ingestion` etc.), kept
separate from the `@huey.task()` wrapper, so tests and the manual "retry"
endpoint can call the logic directly/synchronously without needing Huey's
immediate-mode machinery.

Checkpointing & resume (2.A #12, #5): every page transitions
pending -> done|failed and is committed to the DB as it completes. A
(re)run always starts from `get_resume_page_number` — the lowest
page_number not yet 'done' — never from page 1. The one exception is the
running document summary, which is a *cache* rather than a checkpoint: on
resume it's rebuilt by re-folding over already-stored page summaries
before continuing forward (see `_rebuild_running_summary`).
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
from pathlib import Path

from app.config import settings
from app.database import session
from app.models import documents as documents_repo
from app.pipeline.huey_app import huey
from app.services.embedding_service import get_embedding_provider
from app.services.encoding_fix import fix_mojibake
from app.services.keywords import flatten_keywords_for_embedding
from app.services.language_detection import detect_language
from app.services.llm_call import run_prompt
from app.services.ocr_service import (
    OCRExtractionError,
    get_fallback_ocr_provider,
    get_primary_ocr_provider,
)
from app.services.text_stats import count_sentences
from app.services.vector_store import upsert_vector

logger = logging.getLogger("paper_rag.pipeline")


class PageProcessingTimeoutError(RuntimeError):
    """Raised by `_run_with_timeout` when a single `_extract_page_text`/
    `run_prompt` call exceeds `settings.PAGE_PROCESSING_TIMEOUT_SECONDS`
    (ISSUE-014, AGENT_TASKS.md). A plain `RuntimeError` subclass (not a
    bespoke base) so it's caught by every existing `except Exception`
    handler in this module without any of them needing to know about it
    specifically - a timeout should be handled exactly like any other
    page-processing failure, just with a clearer message."""


def _run_with_timeout(fn, *args, timeout_seconds: float, **kwargs):
    """Runs `fn(*args, **kwargs)` on a worker thread and waits at most
    `timeout_seconds` for it. A genuine Python-level "cancel this call"
    doesn't exist for a blocking call (no `signal.alarm` here - this
    pipeline's own callers may not be the main thread, e.g. under
    FastAPI's sync-endpoint threadpool, and `signal.alarm` only works
    from the main thread), so this is the standard workaround: the
    calling code moves on (and, per the module docstring, marks the page
    failed/retryable) even though the abandoned thread may keep running
    in the background until the underlying HTTP call itself times out at
    the `openai` client's own `timeout_seconds` (`app/config.py`'s
    `ProviderSettings.timeout_seconds`) - that's an acceptable trade-off
    for turning a hang into a bounded, retryable failure rather than
    truly killing the in-flight call, which Python cannot do safely for
    arbitrary blocking code.

    Re-raises the original exception (unchanged) if `fn` itself raised
    one; raises `PageProcessingTimeoutError` if it didn't finish in time.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise PageProcessingTimeoutError(
                f"{getattr(fn, '__qualname__', fn)} exceeded {timeout_seconds}s timeout"
            ) from exc


@huey.task()
def ingest_document_task(document_id: str) -> None:
    run_ingestion(document_id)


def run_ingestion(document_id: str) -> None:
    with session() as conn:
        doc = documents_repo.get_document(conn, document_id)
        if doc is None:
            raise ValueError(f"No document with id {document_id!r}")
        documents_repo.update_document_fields(conn, document_id, status="processing", last_error=None)

    try:
        _process_document(document_id)
        with session() as conn:
            documents_repo.update_document_fields(conn, document_id, status="done")
        _embed_document_level_vector(document_id)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure halts the doc, see module docstring
        logger.exception("Ingestion failed for document %s", document_id)
        with session() as conn:
            documents_repo.update_document_fields(conn, document_id, status="failed", last_error=str(exc))
        raise


def _process_document(document_id: str) -> None:
    with session() as conn:
        doc = documents_repo.get_document(conn, document_id)
        total_pages = doc["total_pages"]
        pdf_path = Path(doc["file_path"])
        resume_from = documents_repo.get_resume_page_number(conn, document_id)

    if resume_from is None:
        return  # every page already done - nothing to do (idempotent re-run)

    running_summary = _rebuild_running_summary(document_id, resume_from)

    # Covers the case where the pages metadata needs are already 'done'
    # from a previous run but the metadata call itself failed/was never
    # reached before the document was marked failed - see module docstring.
    _maybe_extract_metadata(document_id)

    for page_number in range(resume_from, total_pages + 1):
        running_summary = _process_single_page(document_id, pdf_path, page_number, running_summary)
        _maybe_extract_metadata(document_id)


def _rebuild_running_summary(document_id: str, resume_from: int) -> str | None:
    with session() as conn:
        prior_summaries = documents_repo.get_done_page_summaries_before(conn, document_id, resume_from)
    if not prior_summaries:
        return None

    running_summary: str | None = None
    for page_number, page_summary in prior_summaries:
        result = _run_with_timeout(
            run_prompt,
            "ingestion/doc_summary_fold",
            timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS,
            running_summary=running_summary,
            next_page_summary=page_summary,
            page_number=page_number,
            document_title=None,
        )
        running_summary = result["running_summary"]

    with session() as conn:
        documents_repo.update_document_fields(conn, document_id, running_summary=running_summary)
    return running_summary


def _maybe_extract_metadata(document_id: str) -> None:
    required_count = settings.METADATA_SOURCE_PAGE_COUNT
    with session() as conn:
        doc = documents_repo.get_document(conn, document_id)
        if doc["metadata_status"] != "pending":
            return
        required_count = min(required_count, doc["total_pages"])
        source_pages = documents_repo.list_pages(conn, document_id)[:required_count]

    if len(source_pages) < required_count or any(p["processing_status"] != "done" for p in source_pages):
        return  # not all metadata-source pages are done yet

    combined_text = "\n\n".join(p["content_text"] for p in source_pages if p.get("content_text"))

    # ISSUE-007 (AGENT_TASKS.md): metadata degrades to N/A whenever *any*
    # of the source pages used the pypdf fallback extractor, not only
    # when there's literally no text at all. The PRD's extraction-
    # strategy note groups metadata with summary/keywords as things that
    # are "left as N/A rather than attempted from a degraded input" once
    # the VLM pipeline has failed for a page — `_process_single_page`
    # already enforces exactly this for summary/keywords (gated on
    # `extractor_used == "vlm"`), so metadata follows the same rule
    # rather than the looser "is there any text at all" check this used
    # to have. A fallback page still has real, readable pypdf text, but
    # attempting an LLM extraction call against a degraded, non-VLM
    # input is exactly what the PRD says not to do.
    used_fallback = any(p.get("extractor_used") != "vlm" for p in source_pages)

    if not combined_text.strip() or used_fallback:
        with session() as conn:
            documents_repo.set_document_metadata(
                conn,
                document_id,
                doc_type=None,
                authors=None,
                year=None,
                title=None,
                venue=None,
                doi=None,
                acronym=None,
                metadata_status="na",
            )
        return

    result = _run_with_timeout(
        run_prompt,
        "ingestion/metadata_extract",
        timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS,
        combined_text=combined_text,
        page_count=len(source_pages),
    )
    language = detect_language(combined_text)

    with session() as conn:
        documents_repo.set_document_metadata(
            conn,
            document_id,
            doc_type=result.get("doc_type") or None,
            authors=[a for a in (result.get("authors") or []) if a] or None,
            year=result.get("year") or None,
            title=result.get("title") or None,
            venue=result.get("venue") or None,
            doi=result.get("doi") or None,
            acronym=result.get("acronym") or None,
            metadata_status="done",
        )
        documents_repo.update_document_fields(conn, document_id, language=language)


def _process_single_page(document_id: str, pdf_path: Path, page_number: int, running_summary: str | None) -> str | None:
    from app.utils.hashing import make_page_id

    page_id = make_page_id(document_id, page_number)

    with session() as conn:
        existing = documents_repo.get_page(conn, document_id, page_number)
    if existing and existing["processing_status"] == "done":
        # Idempotent guard - see module docstring. Carry the existing
        # summary forward into the fold rather than reprocessing.
        if existing.get("page_summary"):
            result = _run_with_timeout(
                run_prompt,
                "ingestion/doc_summary_fold",
                timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS,
                running_summary=running_summary,
                next_page_summary=existing["page_summary"],
                page_number=page_number,
                document_title=None,
            )
            running_summary = result["running_summary"]
            with session() as conn:
                documents_repo.update_document_fields(conn, document_id, running_summary=running_summary)
        return running_summary

    try:
        raw_text, extractor_used = _extract_page_text(pdf_path, page_number)
    except Exception as exc:  # noqa: BLE001 - both primary and fallback failed (including a timeout - see PageProcessingTimeoutError)
        with session() as conn:
            documents_repo.update_page_fields(
                conn, page_id, processing_status="failed", error_message=str(exc)
            )
        raise

    fixed_text, was_fixed = fix_mojibake(raw_text)

    is_short = False
    page_summary: str | None = None
    keywords: dict | None = None

    if extractor_used == "vlm":
        if count_sentences(fixed_text) < settings.SHORT_PAGE_SENTENCE_THRESHOLD:
            is_short = True
        else:
            # ISSUE-014 (AGENT_TASKS.md): unlike the extraction step above,
            # these two run_prompt calls previously had no exception
            # handling at all - a failure (or, before this fix, a hang)
            # here would leave the page stuck at whatever partial DB
            # state it already had (still "pending"), invisible as
            # failed and not retryable via get_resume_page_number, which
            # only resumes *forward* from the first non-done page - the
            # exact "hang" this issue is about, just manifesting as a
            # stuck page instead of a stuck process. Mirror the
            # extraction step's pattern: mark the page failed and
            # re-raise so it surfaces in the dashboard and is retryable.
            try:
                page_summary = _run_with_timeout(
                    run_prompt,
                    "ingestion/page_summary",
                    timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS,
                    page_text=fixed_text,
                    page_number=page_number,
                    max_sentences=5,
                )["summary"]
                keywords = _run_with_timeout(
                    run_prompt,
                    "ingestion/page_keywords",
                    timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS,
                    page_text=fixed_text,
                    page_number=page_number,
                )
            except Exception as exc:  # noqa: BLE001 - summary/keywords generation failed or timed out
                with session() as conn:
                    documents_repo.update_page_fields(
                        conn, page_id, processing_status="failed", error_message=str(exc)
                    )
                raise

    with session() as conn:
        documents_repo.update_page_fields(
            conn,
            page_id,
            content_text=fixed_text,
            content_text_fixed=1 if was_fixed else 0,
            extractor_used=extractor_used,
            is_short_page=1 if is_short else 0,
            page_summary=page_summary,
            keywords_json=json.dumps(keywords) if keywords else None,
            processing_status="done",
            error_message=None,
        )
        page_rowid = documents_repo.get_page_rowid(conn, page_id)

        embedder = get_embedding_provider()
        if fixed_text.strip():
            content_vec = embedder.embed([fixed_text])[0]
            upsert_vector(conn, "page_content_vec", page_rowid, content_vec)
        if page_summary:
            summary_vec = embedder.embed([page_summary])[0]
            upsert_vector(conn, "page_summary_vec", page_rowid, summary_vec)
        if keywords:
            keyword_text = flatten_keywords_for_embedding(keywords)
            if keyword_text.strip():
                keywords_vec = embedder.embed([keyword_text])[0]
                upsert_vector(conn, "page_keywords_vec", page_rowid, keywords_vec)

    if page_summary:
        # Note: the page row above is already committed "done" by this
        # point (real extracted content/summary/keywords/embeddings all
        # saved) - if this fold call times out or fails, that failure
        # propagates up to fail the *document* (run_ingestion's catch-
        # all), not this page. That's intentional, not a gap: this page
        # doesn't need to be redone on retry, and `_rebuild_running_summary`
        # already re-folds every done page's summary from scratch on
        # resume (see its docstring / the module docstring's "cache, not
        # a checkpoint" note), so a retry correctly regenerates
        # running_summary without reprocessing this page.
        fold_result = _run_with_timeout(
            run_prompt,
            "ingestion/doc_summary_fold",
            timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS,
            running_summary=running_summary,
            next_page_summary=page_summary,
            page_number=page_number,
            document_title=None,
        )
        running_summary = fold_result["running_summary"]
        with session() as conn:
            documents_repo.update_document_fields(conn, document_id, running_summary=running_summary)

    return running_summary


def _extract_page_text(pdf_path: Path, page_number: int) -> tuple[str, str]:
    """Returns (text, extractor_used). Tries the VLM primary path first;
    only falls back to pypdf if the primary raises OCRExtractionError
    (PRD 2.A #1's "worst case" fallback). If the fallback *also* fails, the
    exception propagates and the page is marked 'failed'.

    Each attempt gets its own full `PAGE_PROCESSING_TIMEOUT_SECONDS`
    budget (ISSUE-014, AGENT_TASKS.md) rather than sharing one budget
    across both - a slow-but-eventually-`OCRExtractionError`-raising
    primary shouldn't eat into the fallback's own allowance."""
    primary = get_primary_ocr_provider()
    try:
        result = _run_with_timeout(
            primary.extract_page, pdf_path, page_number, timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS
        )
        return result.text, "vlm"
    except OCRExtractionError:
        logger.warning("Primary OCR failed on page %s of %s - falling back to pypdf", page_number, pdf_path)
        fallback = get_fallback_ocr_provider()
        result = _run_with_timeout(
            fallback.extract_page, pdf_path, page_number, timeout_seconds=settings.PAGE_PROCESSING_TIMEOUT_SECONDS
        )
        return result.text, "fallback"


def _embed_document_level_vector(document_id: str) -> None:
    """Writes the one-per-document vector in `document_vec` (title +
    running_summary). This is intentionally not consulted by
    `retrieve_pages()` - see `app/services/document_similarity.py`'s
    module docstring (ISSUE-009, AGENT_TASKS.md) for what this table is
    for instead and why."""
    with session() as conn:
        doc = documents_repo.get_document(conn, document_id)
        text = "\n\n".join(part for part in (doc.get("title"), doc.get("running_summary")) if part)
        if not text.strip():
            return
        embedder = get_embedding_provider()
        vec = embedder.embed([text])[0]
        doc_rowid = documents_repo.get_document_rowid(conn, document_id)
        upsert_vector(conn, "document_vec", doc_rowid, vec)

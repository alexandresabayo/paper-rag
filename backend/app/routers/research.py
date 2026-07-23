"""
Research (the researcher-facing RAG) router — PRD Section 2.B.

`answer_mode` (2.B #4) is the manual, binary switch upstream of and
separate from the automatic scenario classifier (2.B #2):
  - "full_rag": retrieval runs, then one of the four scenarios applies
    based on the *combined* retrieval confidence (see
    app/services/retrieval_service.py).
  - "direct_model": retrieval is skipped entirely - a plain LLM answer,
    no document context, no scenario at all. This is not the same as the
    automatic "model_only" scenario, which still ran retrieval and found
    nothing sufficiently relevant.

`POST /query` streams its answer as Server-Sent Events (ISSUE-015,
AGENT_TASKS.md) rather than returning one JSON body - see `submit_query`'s
docstring for the event sequence. A plain (synchronous) generator is
deliberately fine here, not an async one: this whole app's DB/pipeline
layer is synchronous raw sqlite3 (see app/database.py's module
docstring), and Starlette's `StreamingResponse` wraps a non-async
iterable in `iterate_in_threadpool` automatically - verified against the
installed Starlette version's source, not assumed - so each blocking step
below (retrieval, the generation call, the final DB write) still runs off
the event loop without this module needing any async/await of its own.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.database import get_db, session
from app.models import documents as documents_repo
from app.models import queries as queries_repo
from app.schemas.research import (
    HistoryItem,
    HistoryResponse,
    QueryDoneEvent,
    QueryErrorEvent,
    QueryMetaEvent,
    QueryRequest,
    SourceHit,
)
from app.services.llm_call import run_prompt_stream
from app.services.retrieval_service import classify_scenario, retrieve_pages

router = APIRouter(prefix="/api/research", tags=["research"])


def _sse(event: str, payload) -> str:
    """One Server-Sent-Event message. `payload` is a Pydantic model,
    serialized with its own `.model_dump_json()` rather than a bare
    `json.dumps(dict)`, so field types (e.g. the `scenario` Literal) are
    validated on the way out, not just on the way in."""
    return f"event: {event}\ndata: {payload.model_dump_json()}\n\n"


@router.post("/query")
def submit_query(request: QueryRequest, db: sqlite3.Connection = Depends(get_db)) -> StreamingResponse:
    """Streams three (or four) SSE events in order:

    1. `meta` - id, query_text, answer_mode, scenario, sources. Retrieval
       and scenario classification have already both happened by this
       point, so the citation list can render immediately, well before
       the answer text finishes.
    2. `chunk` (zero or more) - one incremental piece of answer text each.
    3. `done` - the authoritative full answer text plus `created_at`,
       sent immediately after the query is persisted to history.

    ...or, if something fails partway through generation (after the
    response's 200 status/headers are already committed, so it can't
    become a clean HTTP error at that point):

    4. `error` - in place of any further `chunk`/`done` events. Nothing
       is persisted to history in this case, mirroring the old
       non-streaming endpoint's behavior of never writing a query row
       when generation itself raised.
    """
    query_id = str(uuid.uuid4())

    if request.answer_mode == "direct_model":
        # 2.B #4: retrieval skipped entirely, no scenario classification at all.
        scenario = None
        sources: list[SourceHit] = []
        prompt_name = "research/direct_model"
        prompt_variables = {"query": request.query_text}
    else:
        hits = retrieve_pages(db, request.query_text)
        scenario = classify_scenario(hits)
        retrieved_context = (
            []
            if scenario == "model_only"
            else [
                {
                    "document_title": h.document_title,
                    "page_number": h.page_number,
                    "similarity_score": h.similarity_score,
                    "snippet": h.snippet,
                }
                for h in hits
            ]
        )
        # Sources are always surfaced to the UI (even for model_only, at low
        # confidence) so the "understated similarity score" caption in the
        # Design section has something to show - the *prompt* is what
        # withholds weak context from the model, not the API response.
        sources = [
            SourceHit(
                document_id=h.document_id,
                document_title=h.document_title,
                page_number=h.page_number,
                similarity_score=h.similarity_score,
                snippet=h.snippet,
            )
            for h in hits
        ]
        prompt_name = "research/answer_generation"
        prompt_variables = {
            "query": request.query_text,
            "scenario": scenario,
            "retrieved_context": retrieved_context,
        }

    meta_event = QueryMetaEvent(
        id=query_id,
        query_text=request.query_text,
        answer_mode=request.answer_mode,
        scenario=scenario,
        sources=sources,
    )

    def event_stream() -> Iterator[str]:
        yield _sse("meta", meta_event)

        chunks: list[str] = []
        try:
            for piece in run_prompt_stream(prompt_name, **prompt_variables):
                chunks.append(piece)
                yield f"event: chunk\ndata: {json.dumps({'text': piece})}\n\n"
        except Exception as exc:  # noqa: BLE001 - see docstring: can't become a clean HTTP error mid-stream
            yield _sse("error", QueryErrorEvent(message=str(exc)))
            return

        response_text = "".join(chunks)

        with session() as conn:
            queries_repo.create_query(
                conn,
                query_id=query_id,
                query_text=request.query_text,
                response_text=response_text,
                answer_mode=request.answer_mode,
                scenario=scenario,
                retrieved_pages_json=json.dumps([s.model_dump() for s in sources]),
            )
            row = queries_repo.get_query(conn, query_id)

        yield _sse("done", QueryDoneEvent(response_text=response_text, created_at=row["created_at"]))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/history", response_model=HistoryResponse)
def get_history(limit: int = 50, offset: int = 0, db: sqlite3.Connection = Depends(get_db)) -> HistoryResponse:
    rows = queries_repo.list_queries(db, limit=limit, offset=offset)
    return HistoryResponse(
        items=[
            HistoryItem(
                id=r["id"],
                query_text=r["query_text"],
                response_text=r["response_text"],
                answer_mode=r["answer_mode"],
                scenario=r["scenario"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
    )


@router.get("/documents/{document_id}/pdf")
def serve_pdf(document_id: str, db: sqlite3.Connection = Depends(get_db)):
    """PRD 2.B #7 "PDF Document Serving" - serve the original PDF for the
    citation/source viewer."""
    doc = documents_repo.get_document(db, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # content_disposition_type="inline" (Starlette defaults FileResponse
    # to "attachment", which makes browsers download rather than render
    # the file) - ISSUE-017 (AGENT_TASKS.md): a citation's inline PDF
    # viewer embeds this URL in an <iframe>, which needs "inline" to
    # actually display the PDF instead of triggering a download inside
    # the frame. Verified against the installed Starlette version's
    # FileResponse source, not assumed.
    return FileResponse(
        doc["file_path"],
        media_type="application/pdf",
        filename=doc["file_name"],
        content_disposition_type="inline",
    )

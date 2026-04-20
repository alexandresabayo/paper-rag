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
"""

from __future__ import annotations

import json
import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.database import get_db, session
from app.models import documents as documents_repo
from app.models import queries as queries_repo
from app.schemas.research import HistoryItem, HistoryResponse, QueryRequest, QueryResponse, SourceHit
from app.services.llm_call import run_prompt
from app.services.retrieval_service import classify_scenario, retrieve_pages

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/query", response_model=QueryResponse)
def submit_query(request: QueryRequest, db: sqlite3.Connection = Depends(get_db)) -> QueryResponse:
    query_id = str(uuid.uuid4())

    if request.answer_mode == "direct_model":
        # 2.B #4: retrieval skipped entirely, no scenario classification at all.
        result = run_prompt("research/direct_model", query=request.query_text)
        response_text = result["answer"]
        scenario = None
        sources: list[SourceHit] = []
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
        result = run_prompt(
            "research/answer_generation",
            query=request.query_text,
            scenario=scenario,
            retrieved_context=retrieved_context,
        )
        response_text = result["answer"]
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

    return QueryResponse(
        id=query_id,
        query_text=request.query_text,
        response_text=response_text,
        answer_mode=request.answer_mode,
        scenario=scenario,
        sources=sources,
        created_at=row["created_at"],
    )


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
    return FileResponse(doc["file_path"], media_type="application/pdf", filename=doc["file_name"])

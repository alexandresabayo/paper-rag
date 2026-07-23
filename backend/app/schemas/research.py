from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query_text: str = Field(min_length=1)
    # 2.B #4: manual, binary switch, upstream of and separate from the
    # automatic scenario classifier.
    answer_mode: Literal["full_rag", "direct_model"] = "full_rag"


class SourceHit(BaseModel):
    document_id: str
    document_title: str
    page_number: int
    similarity_score: float
    snippet: str


class QueryMetaEvent(BaseModel):
    """First SSE event for a query (ISSUE-015, AGENT_TASKS.md): everything
    known before generation begins - retrieval and scenario
    classification both already happened by this point. `response_text`
    isn't here; it arrives incrementally as `chunk` events, then once
    more, authoritatively, in `QueryDoneEvent`."""

    id: str
    query_text: str
    answer_mode: Literal["full_rag", "direct_model"]
    scenario: Literal["database_only", "hybrid", "model_first", "model_only"] | None
    sources: list[SourceHit]


class QueryChunkEvent(BaseModel):
    """One incremental piece of the answer's text."""

    text: str


class QueryDoneEvent(BaseModel):
    """Final SSE event: the authoritative, complete answer text (the
    client's own concatenation of `chunk` events should already match
    this, but the client trusts this value, not its own concatenation -
    a defensive stance against any chunking edge case), plus the
    `created_at` timestamp assigned when the query was persisted to
    history immediately beforehand."""

    response_text: str
    created_at: str


class QueryErrorEvent(BaseModel):
    """Terminal SSE event for a failure that happens *after* streaming
    has already started (e.g. mid-generation) - by that point the HTTP
    status/headers are already committed as a 200, so a failure can't
    become a clean 4xx/5xx the way it can before the first byte goes
    out. The client treats this the same as a network-level failure."""

    message: str


class HistoryItem(BaseModel):
    id: str
    query_text: str
    response_text: str | None
    answer_mode: str
    scenario: str | None
    created_at: str


class HistoryResponse(BaseModel):
    items: list[HistoryItem]

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


class QueryResponse(BaseModel):
    id: str
    query_text: str
    response_text: str
    answer_mode: Literal["full_rag", "direct_model"]
    scenario: Literal["database_only", "hybrid", "model_first", "model_only"] | None
    sources: list[SourceHit]
    created_at: str


class HistoryItem(BaseModel):
    id: str
    query_text: str
    response_text: str | None
    answer_mode: str
    scenario: str | None
    created_at: str


class HistoryResponse(BaseModel):
    items: list[HistoryItem]

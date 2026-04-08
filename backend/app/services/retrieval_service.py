"""
Semantic retrieval + scenario classification — PRD 2.B #1 and #2.

Retrieval combines three independently-searched embedding sources per page
(content, summary, keywords — Section 3 "Embedding Model Selection") with
configurable weights (app/config.py) into one ranked list — the "Precision
Re-ranking" beyond any single vec0 table's own ANN ordering. Each source is
over-fetched (`_CANDIDATE_MULTIPLIER`) before combining, so a page that
ranks highly on e.g. keyword-similarity alone still gets a chance to
surface even if it wasn't in another source's raw top-k.

Scenario classification (2.B #2) then looks at the *combined* top score
against configurable thresholds. See app/config.py's docstring on
`SCENARIO_*_THRESHOLD` for the "dynamic thresholding" caveat.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.config import settings
from app.services import vector_store
from app.services.embedding_service import get_embedding_provider

_CANDIDATE_MULTIPLIER = 4
_MIN_CANDIDATES = 20

_SOURCE_TABLES_AND_WEIGHTS = (
    ("page_content_vec", "EMBEDDING_WEIGHT_CONTENT"),
    ("page_summary_vec", "EMBEDDING_WEIGHT_SUMMARY"),
    ("page_keywords_vec", "EMBEDDING_WEIGHT_KEYWORDS"),
)


@dataclass(frozen=True)
class RetrievalHit:
    document_id: str
    document_title: str
    page_number: int
    similarity_score: float  # combined, weighted cosine similarity, ~0..1
    snippet: str


def retrieve_pages(conn: sqlite3.Connection, query_text: str, top_k: int | None = None) -> list[RetrievalHit]:
    top_k = top_k or settings.RETRIEVAL_TOP_K
    candidate_k = max(top_k * _CANDIDATE_MULTIPLIER, _MIN_CANDIDATES)

    embedder = get_embedding_provider()
    query_vector = embedder.embed([query_text])[0]

    # rowid -> cosine_similarity, one dict per source
    per_source_similarities: dict[str, dict[int, float]] = {}
    for table, weight_attr in _SOURCE_TABLES_AND_WEIGHTS:
        hits = vector_store.search(conn, table, query_vector, candidate_k)
        per_source_similarities[weight_attr] = {rowid: 1.0 - distance for rowid, distance in hits}

    all_rowids: set[int] = set()
    for sims in per_source_similarities.values():
        all_rowids.update(sims.keys())

    combined_scores: dict[int, float] = {}
    for rowid in all_rowids:
        score = 0.0
        for weight_attr, sims in per_source_similarities.items():
            if rowid in sims:
                score += getattr(settings, weight_attr) * sims[rowid]
        combined_scores[rowid] = score

    ranked_rowids = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

    hits: list[RetrievalHit] = []
    for rowid, score in ranked_rowids:
        row = conn.execute(
            """
            SELECT p.document_id, p.page_number, p.page_summary, p.content_text,
                   d.title AS document_title, d.file_name
            FROM pages p
            JOIN documents d ON d.id = p.document_id
            WHERE p.rowid = ?
            """,
            (rowid,),
        ).fetchone()
        if row is None:
            continue  # stale vector row (shouldn't happen; defensive)
        snippet_source = row["page_summary"] or row["content_text"] or ""
        hits.append(
            RetrievalHit(
                document_id=row["document_id"],
                document_title=row["document_title"] or row["file_name"],
                page_number=row["page_number"],
                similarity_score=round(score, 4),
                snippet=snippet_source[:600],
            )
        )
    return hits


def classify_scenario(hits: list[RetrievalHit]) -> str:
    """One of 'database_only' | 'hybrid' | 'model_first' | 'model_only'."""
    if not hits:
        return "model_only"
    top_score = hits[0].similarity_score
    if top_score >= settings.SCENARIO_HIGH_THRESHOLD:
        return "database_only"
    if top_score >= settings.SCENARIO_MID_THRESHOLD:
        return "hybrid"
    if top_score >= settings.SCENARIO_LOW_THRESHOLD:
        return "model_first"
    return "model_only"

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
against configurable thresholds (app/config.py's `SCENARIO_*_THRESHOLD`),
plus one dynamic adjustment on top - see `classify_scenario` and
`SCENARIO_MARGIN_THRESHOLD`'s docstring in app/config.py (ISSUE-008,
AGENT_TASKS.md) for why a static top-score cutoff alone isn't "dynamic"
and what's layered on top of it here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.config import settings
from app.services import vector_store
from app.services.embedding_service import get_embedding_provider

_CANDIDATE_MULTIPLIER = 4
_MIN_CANDIDATES = 20

# Ordered from highest to lowest retrieval confidence, so
# classify_scenario's margin-based demotion can simply step one entry to
# the right (never past the end - model_only has nowhere lower to go).
_SCENARIO_TIERS = ("database_only", "hybrid", "model_first", "model_only")

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
    """One of 'database_only' | 'hybrid' | 'model_first' | 'model_only'.

    Two passes (ISSUE-008, AGENT_TASKS.md):

    1. Base tier from the top hit's absolute combined score against the
       static `SCENARIO_*_THRESHOLD` cutoffs - unchanged from before.
    2. Dynamic adjustment: if the top hit doesn't clear the runner-up by
       at least `SCENARIO_MARGIN_THRESHOLD`, demote one tier. A high top
       score that's basically tied with several other candidates is
       weaker evidence of "this page specifically answers the question"
       than the same top score with daylight between it and the rest of
       the ranked list - the *shape* of the ranked list, not just its
       highest value, is what makes this "dynamic" per query rather than
       a single fixed cutoff. Only ever demotes, never promotes: a low
       top score isn't rescued by a large gap under it, since the gap
       alone says nothing about whether the top hit is any good.
    """
    if not hits:
        return "model_only"

    top_score = hits[0].similarity_score
    if top_score >= settings.SCENARIO_HIGH_THRESHOLD:
        tier_index = 0  # database_only
    elif top_score >= settings.SCENARIO_MID_THRESHOLD:
        tier_index = 1  # hybrid
    elif top_score >= settings.SCENARIO_LOW_THRESHOLD:
        tier_index = 2  # model_first
    else:
        tier_index = 3  # model_only

    if tier_index < len(_SCENARIO_TIERS) - 1 and len(hits) > 1:
        margin = top_score - hits[1].similarity_score
        if margin < settings.SCENARIO_MARGIN_THRESHOLD:
            tier_index += 1

    return _SCENARIO_TIERS[tier_index]

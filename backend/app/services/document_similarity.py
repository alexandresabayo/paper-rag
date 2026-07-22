"""
Document-level similarity — the read side of `document_vec` (ISSUE-009,
AGENT_TASKS.md).

`document_vec` has existed since the original schema (PRD Section 4's
"Vector Collection" entity lists "Document embeddings" as a peer of
"Page-level embeddings", not an afterthought) and has been written to
since the first version of the ingestion pipeline
(`app.pipeline.tasks._embed_document_level_vector`, one vector per
document from its title + running_summary). Until this module, nothing
ever *read* it back - a write-only table with no consumer to prove it
round-trips.

Deciding its fate (ISSUE-009) came down to two options: wire it into
`retrieve_pages()` as a document-level pre-filter ahead of the per-page
search, or give it a real, separate purpose. Pre-filtering was rejected:
this is a personal/small-team corpus (README), not an enterprise-scale
one where per-page ANN search over every page needs a coarse first pass
to stay fast, and PRD 2.B #1 defines retrieval as page-level - narrowing
to a top-N *document* shortlist first risks silently dropping a genuinely
relevant page that lives in an otherwise low-scoring document, for a
speed problem this corpus doesn't have.

Instead, `document_vec` is exactly what PRD Section 7 needs for the
deferred **"Topic exploration & cartography"** feature - "a thematic
exploration/mapping view across the document corpus, letting users
browse by theme rather than only ask questions... revisit once the core
RAG pipeline (ingestion, retrieval, chatbot) is stable." A theme map or
"documents similar to this one" view needs per-document vectors to
cluster or plot, not per-page ones - that's what this table has been for
all along.

`find_similar_documents()` below is the first real read-side consumer,
proving the write side actually round-trips (see
tests/test_document_similarity.py). It is deliberately NOT called from
any router yet - Section 7 explicitly defers the feature that would use
it, and this module intentionally does not get ahead of that decision by
inventing an early "related documents" UI element off the side of
Research or Ingestion.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.services import vector_store
from app.services.embedding_service import get_embedding_provider


@dataclass(frozen=True)
class DocumentSimilarityHit:
    document_id: str
    document_title: str
    similarity_score: float  # cosine similarity, ~0..1


def find_similar_documents(conn: sqlite3.Connection, query_text: str, top_k: int = 10) -> list[DocumentSimilarityHit]:
    """Nearest documents to `query_text` by their document-level vector
    (title + running_summary, see `_embed_document_level_vector`).

    `query_text` is deliberately generic rather than "a document id to
    find neighbors of" - the same primitive supports both "documents
    similar to this one" (caller passes that document's own title/summary
    text) and a free-text thematic search once Section 7's cartography
    view exists, without needing two near-identical functions.

    Returns `[]` for a corpus nothing has been embedded into yet, same
    as `vector_store.search()` - no vec0 table existing yet is a normal
    state, not an error (see vector_store.py's module docstring).
    """
    embedder = get_embedding_provider()
    query_vector = embedder.embed([query_text])[0]

    raw_hits = vector_store.search(conn, "document_vec", query_vector, top_k)

    hits: list[DocumentSimilarityHit] = []
    for rowid, distance in raw_hits:
        row = conn.execute(
            "SELECT id, title, file_name FROM documents WHERE rowid = ?",
            (rowid,),
        ).fetchone()
        if row is None:
            continue  # stale vector row (shouldn't happen; defensive, same as retrieval_service.py)
        hits.append(
            DocumentSimilarityHit(
                document_id=row["id"],
                document_title=row["title"] or row["file_name"],
                similarity_score=round(1.0 - distance, 4),
            )
        )
    return hits

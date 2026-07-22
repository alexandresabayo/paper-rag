from __future__ import annotations

"""
ISSUE-009 (AGENT_TASKS.md): document_vec has been written to by the
ingestion pipeline since the original schema but had no read-side
consumer. See app/services/document_similarity.py's module docstring for
the fate decision (kept, as infra for PRD Section 7's deferred "Topic
exploration & cartography" feature) and why it's not wired into
per-page retrieval.
"""


def test_find_similar_documents_round_trips_the_write_side(tmp_workspace):
    """First real proof the write side (`_embed_document_level_vector`)
    and the read side (`find_similar_documents`) agree with each other."""
    from app.database import session
    from app.models import documents as documents_repo
    from app.pipeline.tasks import _embed_document_level_vector
    from app.services.document_similarity import find_similar_documents

    with session() as conn:
        documents_repo.create_document(
            conn, document_id="doc-a", file_name="a.pdf", file_path="/tmp/a.pdf", total_pages=1
        )
        documents_repo.update_document_fields(
            conn, "doc-a", title="Attention Is All You Need", running_summary="A summary about transformers."
        )
        documents_repo.create_document(
            conn, document_id="doc-b", file_name="b.pdf", file_path="/tmp/b.pdf", total_pages=1
        )
        documents_repo.update_document_fields(
            conn, "doc-b", title="A Totally Unrelated Cooking Guide", running_summary="A summary about baking bread."
        )

    _embed_document_level_vector("doc-a")
    _embed_document_level_vector("doc-b")

    with session() as conn:
        # MockEmbeddingProvider is deterministic (identical text -> identical
        # vector), so querying with doc-a's own title+summary text should
        # surface doc-a first with a perfect similarity score.
        hits = find_similar_documents(conn, "Attention Is All You Need\n\nA summary about transformers.", top_k=5)

    assert hits, "expected at least one hit"
    assert hits[0].document_id == "doc-a"
    assert hits[0].document_title == "Attention Is All You Need"
    assert hits[0].similarity_score == 1.0
    assert any(h.document_id == "doc-b" for h in hits)


def test_find_similar_documents_before_any_document_embedded_is_empty(tmp_workspace):
    """No document_vec table yet - degrades to [] rather than raising,
    consistent with vector_store.search()'s "table doesn't exist yet"
    handling (see test_retrieval_service.py's equivalent page-level
    test)."""
    from app.database import get_connection
    from app.services.document_similarity import find_similar_documents

    conn = get_connection()
    hits = find_similar_documents(conn, "anything at all")
    assert hits == []
    conn.close()


def test_document_vec_populated_end_to_end_through_real_ingestion(client, sample_pdf_bytes):
    """Sanity check through the actual HTTP ingestion flow (not just the
    lower-level helper calls above): document_vec ends up with exactly
    one row per successfully ingested document."""
    import io

    from app.database import get_connection
    from app.services import vector_store

    client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )

    conn = get_connection()
    assert vector_store.table_row_count(conn, "document_vec") == 1
    conn.close()

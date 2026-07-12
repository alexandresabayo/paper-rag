from __future__ import annotations


def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,)
    ).fetchone()
    return row is not None


_ALL_VEC_TABLES = ("page_content_vec", "page_summary_vec", "page_keywords_vec", "document_vec")


def test_vec0_tables_do_not_exist_until_first_upsert(tmp_workspace):
    """Core of the lazy-schema-creation lifecycle: a fresh DB (post
    init_db(), pre-ingestion) has none of the four vec0 tables yet - they
    only get created the first time something is actually embedded."""
    from app.database import get_connection

    conn = get_connection()
    for table in _ALL_VEC_TABLES:
        assert not _table_exists(conn, table), f"{table} should not exist before any upsert"
    conn.close()


def test_search_before_any_upsert_returns_empty_not_error(tmp_workspace):
    """A query against a never-ingested-into DB must degrade to an empty
    result list, not raise - this is what lets retrieve_pages() resolve
    to the 'model_only' scenario for an empty corpus (see
    test_research_flow.py::test_full_rag_with_empty_corpus_is_model_only)."""
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    results = vector_store.search(conn, "page_content_vec", [1.0, 0.0, 0.0, 0.0], k=5)
    assert results == []
    assert vector_store.table_row_count(conn, "page_content_vec") == 0
    conn.close()


def test_delete_before_any_upsert_is_a_noop(tmp_workspace):
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    vector_store.delete_vector(conn, "page_content_vec", 999)  # must not raise
    conn.close()


def test_first_upsert_creates_all_four_tables_sized_to_that_vector(tmp_workspace):
    """All four vec0 tables are created together, from whichever one is
    touched first - they always share one embedding provider's dimension,
    so there's no reason to stagger their creation."""
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    dim = 6
    vector_store.upsert_vector(conn, "page_summary_vec", 1, [0.1] * dim)
    conn.commit()

    for table in _ALL_VEC_TABLES:
        assert _table_exists(conn, table), f"{table} should exist after the first upsert"

    # And the *other* tables are now genuinely queryable at that width too,
    # even though nothing has been upserted into them specifically yet.
    assert vector_store.search(conn, "page_content_vec", [0.0] * dim, k=5) == []
    conn.close()


def test_vector_upsert_and_search_roundtrip(tmp_workspace):
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    vector_store.upsert_vector(conn, "page_content_vec", 1, [1.0, 0.0, 0.0, 0.0])
    vector_store.upsert_vector(conn, "page_content_vec", 2, [0.0, 1.0, 0.0, 0.0])
    conn.commit()

    results = vector_store.search(conn, "page_content_vec", [1.0, 0.0, 0.0, 0.0], k=2)
    assert results[0][0] == 1
    assert results[0][1] == 0.0  # identical vector -> cosine distance 0
    conn.close()


def test_vector_upsert_overwrites_existing_rowid(tmp_workspace):
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    dim = 8
    vector_store.upsert_vector(conn, "page_content_vec", 7, [1.0] + [0.0] * (dim - 1))
    vector_store.upsert_vector(conn, "page_content_vec", 7, [0.0, 1.0] + [0.0] * (dim - 2))
    conn.commit()

    assert vector_store.table_row_count(conn, "page_content_vec") == 1
    results = vector_store.search(conn, "page_content_vec", [0.0, 1.0] + [0.0] * (dim - 2), k=1)
    assert results[0][1] == 0.0
    conn.close()


def test_upsert_inside_a_rolled_back_transaction_undoes_schema_creation_too(tmp_workspace):
    """The whole point of using individual conn.execute() calls (not
    executescript) for the lazy vec0 CREATE statements: they participate
    in the caller's transaction like any other statement, so a failure
    elsewhere in the same `session()` block rolls back the schema
    creation right along with the data - see ensure_vector_schema()'s
    docstring in app/database.py."""
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    vector_store.upsert_vector(conn, "page_content_vec", 1, [1.0, 0.0, 0.0, 0.0])
    conn.rollback()

    for table in _ALL_VEC_TABLES:
        assert not _table_exists(conn, table), f"{table} should not survive a rollback"
    conn.close()


def test_scenario_classification_thresholds():
    from app.services.retrieval_service import RetrievalHit, classify_scenario

    def hit(score: float) -> RetrievalHit:
        return RetrievalHit(document_id="d", document_title="t", page_number=1, similarity_score=score, snippet="s")

    assert classify_scenario([]) == "model_only"
    assert classify_scenario([hit(0.9)]) == "database_only"
    assert classify_scenario([hit(0.6)]) == "hybrid"
    assert classify_scenario([hit(0.4)]) == "model_first"
    assert classify_scenario([hit(0.1)]) == "model_only"

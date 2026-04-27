from __future__ import annotations


def test_vector_upsert_and_search_roundtrip(tmp_workspace):
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    vector_store.upsert_vector(conn, "page_content_vec", 1, [1.0, 0.0, 0.0, 0.0] + [0.0] * (1024 - 4))
    vector_store.upsert_vector(conn, "page_content_vec", 2, [0.0, 1.0, 0.0, 0.0] + [0.0] * (1024 - 4))
    conn.commit()

    results = vector_store.search(conn, "page_content_vec", [1.0, 0.0, 0.0, 0.0] + [0.0] * (1024 - 4), k=2)
    assert results[0][0] == 1
    assert results[0][1] == 0.0  # identical vector -> cosine distance 0
    conn.close()


def test_vector_upsert_overwrites_existing_rowid(tmp_workspace):
    from app.database import get_connection
    from app.services import vector_store

    conn = get_connection()
    dim = 1024
    vector_store.upsert_vector(conn, "page_content_vec", 7, [1.0] + [0.0] * (dim - 1))
    vector_store.upsert_vector(conn, "page_content_vec", 7, [0.0, 1.0] + [0.0] * (dim - 2))
    conn.commit()

    assert vector_store.table_row_count(conn, "page_content_vec") == 1
    results = vector_store.search(conn, "page_content_vec", [0.0, 1.0] + [0.0] * (dim - 2), k=1)
    assert results[0][1] == 0.0
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

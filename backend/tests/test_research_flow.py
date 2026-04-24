from __future__ import annotations

import io


def _ingest_one(client, sample_pdf_bytes):
    response = client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    return response.json()[0]["document"]["id"]


def test_direct_model_mode_skips_retrieval(client, sample_pdf_bytes):
    _ingest_one(client, sample_pdf_bytes)
    response = client.post(
        "/api/research/query",
        json={"query_text": "What is BGE-M3?", "answer_mode": "direct_model"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_mode"] == "direct_model"
    assert body["scenario"] is None
    assert body["sources"] == []
    assert body["response_text"]


def test_full_rag_mode_returns_a_scenario(client, sample_pdf_bytes):
    _ingest_one(client, sample_pdf_bytes)
    response = client.post(
        "/api/research/query",
        json={"query_text": "Summarize the synthetic test document", "answer_mode": "full_rag"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer_mode"] == "full_rag"
    assert body["scenario"] in ("database_only", "hybrid", "model_first", "model_only")
    assert body["response_text"]


def test_full_rag_with_empty_corpus_is_model_only(client):
    response = client.post(
        "/api/research/query",
        json={"query_text": "Anything at all", "answer_mode": "full_rag"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario"] == "model_only"
    assert body["sources"] == []


def test_query_persists_to_history(client, sample_pdf_bytes):
    client.post("/api/research/query", json={"query_text": "First question", "answer_mode": "direct_model"})
    client.post("/api/research/query", json={"query_text": "Second question", "answer_mode": "direct_model"})

    response = client.get("/api/research/history")
    assert response.status_code == 200
    texts = [item["query_text"] for item in response.json()["items"]]
    assert "First question" in texts
    assert "Second question" in texts


def test_pdf_serving(client, sample_pdf_bytes):
    doc_id = _ingest_one(client, sample_pdf_bytes)
    response = client.get(f"/api/research/documents/{doc_id}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"


def test_rejects_blank_query(client):
    response = client.post("/api/research/query", json={"query_text": ""})
    assert response.status_code == 422

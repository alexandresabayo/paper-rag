from __future__ import annotations

import io
import json


def _ingest_one(client, sample_pdf_bytes):
    response = client.post(
        "/api/ingestion/documents",
        files={"files": ("paper.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")},
    )
    return response.json()[0]["document"]["id"]


def _parse_sse(text: str) -> list[dict]:
    """Splits a raw `text/event-stream` body into a list of
    `{"event": ..., "data": ...}` messages, with `data` already
    JSON-decoded (ISSUE-015, AGENT_TASKS.md)."""
    messages = []
    for raw in text.strip().split("\n\n"):
        if not raw.strip():
            continue
        event = "message"
        data_lines = []
        for line in raw.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not data_lines:
            continue
        messages.append({"event": event, "data": json.loads("\n".join(data_lines))})
    return messages


def _submit_query(client, query_text: str, answer_mode: str = "full_rag") -> list[dict]:
    response = client.post("/api/research/query", json={"query_text": query_text, "answer_mode": answer_mode})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return _parse_sse(response.text)


def test_direct_model_mode_skips_retrieval(client, sample_pdf_bytes):
    _ingest_one(client, sample_pdf_bytes)
    messages = _submit_query(client, "What is BGE-M3?", answer_mode="direct_model")

    events = [m["event"] for m in messages]
    assert events[0] == "meta"
    assert events[-1] == "done"
    assert "chunk" in events  # MockGenerationProvider always yields at least one word

    meta = messages[0]["data"]
    assert meta["answer_mode"] == "direct_model"
    assert meta["scenario"] is None
    assert meta["sources"] == []

    done = messages[-1]["data"]
    assert done["response_text"]
    chunk_text = "".join(m["data"]["text"] for m in messages if m["event"] == "chunk")
    assert done["response_text"] == chunk_text


def test_full_rag_mode_returns_a_scenario(client, sample_pdf_bytes):
    _ingest_one(client, sample_pdf_bytes)
    messages = _submit_query(client, "Summarize the synthetic test document", answer_mode="full_rag")

    meta = messages[0]["data"]
    assert meta["answer_mode"] == "full_rag"
    assert meta["scenario"] in ("database_only", "hybrid", "model_first", "model_only")

    done = messages[-1]["data"]
    assert done["response_text"]


def test_full_rag_with_empty_corpus_is_model_only(client):
    messages = _submit_query(client, "Anything at all", answer_mode="full_rag")
    meta = messages[0]["data"]
    assert meta["scenario"] == "model_only"
    assert meta["sources"] == []


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


def test_pdf_serving_is_inline_not_a_forced_download(client, sample_pdf_bytes):
    """ISSUE-017 (AGENT_TASKS.md): Starlette's FileResponse defaults to
    `Content-Disposition: attachment`, which makes a browser download the
    file rather than render it - that would silently break an <iframe>-
    based inline viewer (it would try to download inside the frame
    instead of displaying the PDF), so this must say "inline"."""
    doc_id = _ingest_one(client, sample_pdf_bytes)
    response = client.get(f"/api/research/documents/{doc_id}/pdf")
    content_disposition = response.headers["content-disposition"]
    assert content_disposition.startswith("inline")


def test_rejects_blank_query(client):
    response = client.post("/api/research/query", json={"query_text": ""})
    assert response.status_code == 422

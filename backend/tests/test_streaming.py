from __future__ import annotations

"""
ISSUE-015 (AGENT_TASKS.md): dedicated tests for the SSE streaming
mechanics themselves (event ordering, mid-stream failure handling) that
don't fit naturally into test_research_flow.py's per-mode tests.
"""

from tests.test_research_flow import _parse_sse, _submit_query


def test_meta_event_arrives_before_any_chunk_or_done(client, sample_pdf_bytes):
    """The whole point of sending sources/scenario in their own first
    event: the citation list can render before any answer text exists."""
    messages = _submit_query(client, "Anything", answer_mode="direct_model")
    assert messages[0]["event"] == "meta"
    assert all(m["event"] != "meta" for m in messages[1:])


def test_chunks_concatenate_to_exactly_the_done_event_text(client, sample_pdf_bytes):
    messages = _submit_query(client, "Anything at all here", answer_mode="direct_model")
    chunk_text = "".join(m["data"]["text"] for m in messages if m["event"] == "chunk")
    done_text = next(m["data"]["response_text"] for m in messages if m["event"] == "done")
    assert chunk_text == done_text
    assert done_text.strip()  # MockGenerationProvider's placeholder is never empty


def test_done_event_is_always_last_on_success(client, sample_pdf_bytes):
    messages = _submit_query(client, "Anything", answer_mode="direct_model")
    assert messages[-1]["event"] == "done"
    assert "created_at" in messages[-1]["data"]


def test_midstream_failure_yields_error_event_instead_of_done(client, monkeypatch):
    """A failure *after* streaming has begun can't become a clean HTTP
    error (status/headers are already committed as 200) - it must show
    up as a terminal `error` SSE event instead."""
    import app.routers.research as research_module

    def flaky_stream(name, **kwargs):
        yield "partial answer text, then... "
        raise RuntimeError("simulated generation failure")

    monkeypatch.setattr(research_module, "run_prompt_stream", flaky_stream)

    response = client.post(
        "/api/research/query",
        json={"query_text": "trigger a failure", "answer_mode": "direct_model"},
    )
    assert response.status_code == 200
    messages = _parse_sse(response.text)

    assert messages[0]["event"] == "meta"
    assert messages[-1]["event"] == "error"
    assert "simulated generation failure" in messages[-1]["data"]["message"]
    assert not any(m["event"] == "done" for m in messages)


def test_midstream_failure_does_not_persist_to_history(client, monkeypatch):
    import app.routers.research as research_module

    def flaky_stream(name, **kwargs):
        yield "partial "
        raise RuntimeError("simulated generation failure")

    monkeypatch.setattr(research_module, "run_prompt_stream", flaky_stream)

    client.post(
        "/api/research/query",
        json={"query_text": "a query that will fail midstream", "answer_mode": "direct_model"},
    )

    history = client.get("/api/research/history").json()["items"]
    assert not any(item["query_text"] == "a query that will fail midstream" for item in history)


def test_rejects_blank_query_before_any_streaming_starts(client):
    """Request validation (Pydantic's min_length=1) happens before the
    endpoint body runs at all, so this must stay a normal JSON 422, not
    an SSE stream."""
    response = client.post("/api/research/query", json={"query_text": ""})
    assert response.status_code == 422
    assert not response.headers["content-type"].startswith("text/event-stream")

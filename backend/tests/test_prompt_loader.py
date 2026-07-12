from __future__ import annotations

import pytest

from app.services.prompt_loader import PromptFormatError, PromptNotFoundError, get_prompt


def test_loads_frontmatter_and_body():
    spec = get_prompt("ingestion/page_summary")
    assert 0 <= spec.temperature <= 1
    assert spec.schema is not None
    assert "summary" in spec.schema["properties"]


def test_render_substitutes_variables():
    spec = get_prompt("ingestion/page_summary")
    rendered = spec.render(page_text="hello world", page_number=3, max_sentences=5)
    assert "hello world" in rendered
    assert "PAGE 3" in rendered


def test_missing_prompt_raises():
    with pytest.raises(PromptNotFoundError):
        get_prompt("does/not/exist")


def test_missing_variable_raises_strict_undefined():
    spec = get_prompt("ingestion/page_summary")
    with pytest.raises(Exception):
        spec.render(page_text="hello")  # missing page_number, max_sentences


def test_all_shipped_prompts_parse():
    names = [
        "ingestion/ocr_transcribe",
        "ingestion/metadata_extract",
        "ingestion/page_summary",
        "ingestion/page_keywords",
        "ingestion/doc_summary_fold",
        "research/answer_generation",
        "research/direct_model",
    ]
    for name in names:
        spec = get_prompt(name)
        assert spec.schema is not None, f"{name} should declare a schema"

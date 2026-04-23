from __future__ import annotations

import pytest

from app.services.json_repair import JSONRepairError, repair_json


def test_parses_clean_json():
    assert repair_json('{"a": 1}') == {"a": 1}


def test_strips_code_fences():
    assert repair_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_slices_outer_braces_from_chatter():
    assert repair_json('Sure, here you go: {"a": 1} hope that helps!') == {"a": 1}


def test_removes_trailing_commas():
    assert repair_json('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_quotes_bareword_keys():
    assert repair_json('{a: "x", b: "y"}') == {"a": "x", "b": "y"}


def test_unrecoverable_raises():
    with pytest.raises(JSONRepairError):
        repair_json("this is not json at all")

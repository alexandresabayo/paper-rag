from __future__ import annotations

from app.services.encoding_fix import fix_mojibake, looks_corrupted


def test_fixes_common_mojibake():
    fixed, changed = fix_mojibake("Ã©tude prÃ©liminaire")
    assert changed
    assert fixed == "étude préliminaire"


def test_no_change_on_clean_text():
    fixed, changed = fix_mojibake("This is perfectly clean text.")
    assert not changed
    assert fixed == "This is perfectly clean text."


def test_looks_corrupted_flags_replacement_char():
    assert looks_corrupted("some text \ufffd\ufffd\ufffd here")


def test_looks_corrupted_false_for_clean_text():
    assert not looks_corrupted("A perfectly normal sentence about physics.")


def test_looks_corrupted_empty_text():
    assert not looks_corrupted("")

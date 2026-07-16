"""Parser tests focus on JSON extraction, since the LLM call itself is networked."""
from src.parser import _extract_json


def test_extract_json_strips_markdown_fences():
    raw = '```json\n{"company": "IONNA", "role_title": "FSE"}\n```'
    assert _extract_json(raw) == '{"company": "IONNA", "role_title": "FSE"}'


def test_extract_json_strips_plain_fences():
    raw = '```\n{"a": 1}\n```'
    assert _extract_json(raw) == '{"a": 1}'


def test_extract_json_finds_object_in_prose():
    raw = 'Here is the result:\n{"a": 1, "b": [2, 3]}\nThanks!'
    assert _extract_json(raw) == '{"a": 1, "b": [2, 3]}'


def test_extract_json_raises_when_missing():
    import pytest

    with pytest.raises(ValueError):
        _extract_json("no json here")

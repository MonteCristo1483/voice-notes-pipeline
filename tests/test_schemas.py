import pytest

from voice_notes.providers import parse_json_text
from voice_notes.schemas import PERSONAL_SHORT_SCHEMA, WORK_SCHEMA, schema_example


def test_schema_example_mirrors_schema_shape():
    example = schema_example(WORK_SCHEMA)

    assert example["essence"] == ""
    assert example["topics"] == [{"title": "", "points": [""]}]
    assert example["tasks"] == [{"task": "", "owner": "", "due": ""}]


def test_personal_schema_example_is_flat():
    example = schema_example(PERSONAL_SHORT_SCHEMA)

    assert set(example) == {"essence", "facts", "actions", "tags"}


def test_parse_json_text_accepts_code_fences():
    assert parse_json_text('```json\n{"essence": "ok"}\n```') == {"essence": "ok"}


def test_parse_json_text_rejects_non_objects():
    with pytest.raises(ValueError):
        parse_json_text('["not", "an", "object"]')

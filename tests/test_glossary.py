import json

from voice_notes.glossary import apply_glossary, load_glossary


def test_glossary_replaces_case_insensitive_forms(tmp_path):
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps({"\\bяпур\\w*": "ЕПУР"}), encoding="utf-8")

    rules = load_glossary(path)

    assert apply_glossary("для Япура и ЯПУР", rules) == "для ЕПУР и ЕПУР"
    assert apply_glossary("ЕПУР уже каноничный", rules) == "ЕПУР уже каноничный"


def test_missing_glossary_is_not_an_error(tmp_path):
    assert load_glossary(tmp_path / "missing.json") == []


def test_invalid_pattern_is_skipped(tmp_path):
    path = tmp_path / "glossary.json"
    path.write_text(json.dumps({"([": "x", "\\bepur": "ЕПУР"}), encoding="utf-8")

    rules = load_glossary(path)

    assert len(rules) == 1
    assert apply_glossary("EPUR", rules) == "ЕПУР"

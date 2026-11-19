from voice_notes.watcher import file_sha1, load_seen, save_seen


def test_sha1_detects_content_changes(tmp_path):
    first = tmp_path / "a.mp3"
    second = tmp_path / "b.mp3"
    first.write_bytes(b"same")
    second.write_bytes(b"different")

    assert file_sha1(first) != file_sha1(second)
    assert file_sha1(first) == file_sha1(first)


def test_seen_registry_roundtrip(tmp_path):
    path = tmp_path / "seen.json"
    data = {"abc": {"name": "note.mp3", "status": "processed", "at": "2026-01-01T10:00:00"}}

    save_seen(path, data)

    assert load_seen(path) == data
    assert load_seen(tmp_path / "missing.json") == {}

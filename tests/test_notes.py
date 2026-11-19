from datetime import datetime
from pathlib import Path

from voice_notes.config import Settings
from voice_notes.notes import note_datetime, safe_filename, write_note
from voice_notes.summarize import _clean_title


def make_settings(tmp_path: Path, vault: Path) -> Settings:
    return Settings(
        work_dir=tmp_path / "work",
        vaults={"personal": vault, "work": vault},
        inboxes={"personal": tmp_path / "inbox", "work": tmp_path / "inbox"},
        whisper_dir=None,
        whisper_exe="faster-whisper-xxl",
        postprocess="postprocess.py",
        ffmpeg="ffmpeg",
    )


def test_note_datetime_prefers_date_from_filename(tmp_path):
    media = tmp_path / "2026-11-19 07-37-53.mp3"
    media.write_bytes(b"x")

    assert note_datetime(media) == datetime(2026, 11, 19, 7, 37, 53)


def test_note_datetime_parses_russian_style_filename(tmp_path):
    media = tmp_path / "Встреча в Телемосте 09.11.26 16-59-19 — запись.webm"
    media.write_bytes(b"x")

    assert note_datetime(media) == datetime(2026, 11, 9, 16, 59, 19)


def test_note_datetime_falls_back_to_mtime(tmp_path):
    media = tmp_path / "Стандартная запись 9.mp3"
    media.write_bytes(b"x")

    result = note_datetime(media)

    assert result.year >= 2020


def test_clean_title_removes_quotes_and_invalid_characters():
    assert _clean_title('«Идея: карта "домов"/районов».', "fallback") == "Идея карта домов районов"
    assert _clean_title("   ", "fallback") == "fallback"


def test_write_note_uses_title_and_recording_date(tmp_path):
    settings = make_settings(tmp_path, tmp_path / "vault")
    media = tmp_path / "2026-11-19 07-37-53.mp3"
    media.write_bytes(b"x")

    path = write_note(
        settings,
        title="Перенос дедлайна и тариф сервера",
        body="## Суть\nТест.",
        transcript="Транскрипт.",
        media_file=media,
        profile="personal",
    )

    text = path.read_text(encoding="utf-8")
    assert path.name == "Перенос дедлайна и тариф сервера.md"
    assert text.startswith("# Перенос дедлайна и тариф сервера\n")
    assert "**Дата:** 2026-11-19 07:37" in text
    assert "Источник" not in text
    assert "Объём транскрипта" not in text


def test_safe_filename_replaces_forbidden_characters():
    assert safe_filename('a/b:c*?"') == "a_b_c___"

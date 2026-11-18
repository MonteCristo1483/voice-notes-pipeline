import os

from voice_notes.config import load_env_file


def test_env_file_does_not_override_existing_values(monkeypatch, tmp_path):
    monkeypatch.setenv("VOICE_NOTES_TEST_KEY", "from-env")
    env = tmp_path / ".env"
    env.write_text(
        "VOICE_NOTES_TEST_KEY=from-file\nVOICE_NOTES_TEST_OTHER=value\n",
        encoding="utf-8",
    )

    load_env_file(env)

    assert os.environ["VOICE_NOTES_TEST_KEY"] == "from-env"
    assert os.environ["VOICE_NOTES_TEST_OTHER"] == "value"


def test_env_file_ignores_comments_and_broken_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\n\nBROKEN LINE\nVOICE_NOTES_OK=1\n", encoding="utf-8")

    load_env_file(env)

    assert os.environ["VOICE_NOTES_OK"] == "1"
    assert "BROKEN LINE" not in os.environ

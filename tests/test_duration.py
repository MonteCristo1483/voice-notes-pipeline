import pytest

from voice_notes.errors import TooShortError
from voice_notes.transcribe import WAV_BYTES_PER_SEC, wav_duration_seconds


def test_wav_duration_uses_pcm_byte_rate(tmp_path):
    wav = tmp_path / "sample.wav"
    wav.write_bytes(b"\0" * WAV_BYTES_PER_SEC * 90)

    assert wav_duration_seconds(wav) == pytest.approx(90.0)


def test_too_short_error_is_informative():
    error = TooShortError(8.2, 60)

    assert error.seconds == pytest.approx(8.2)
    assert "60" in str(error)

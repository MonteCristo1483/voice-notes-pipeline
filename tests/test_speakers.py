from voice_notes.transcribe import normalize_speakers


def test_single_speaker_labels_are_removed():
    text = "**SPEAKER_00**:\nПривет, это заметка.\n\n**SPEAKER_00**:\nВторая реплика."

    assert normalize_speakers(text) == "Привет, это заметка.\n\nВторая реплика."


def test_multiple_speakers_become_readable_labels():
    text = "**SPEAKER_01**:\nПервая реплика.\n\n**SPEAKER_00**:\nОтвет."

    result = normalize_speakers(text)

    assert "SPEAKER" not in result
    assert "Speaker 01: Первая реплика." in result
    assert "Speaker 00: Ответ." in result


def test_inline_speaker_prefix_is_normalized():
    text = "SPEAKER_0: Привет\n\nSPEAKER_1: Здравствуй"
    result = normalize_speakers(text)

    assert "Speaker 0: Привет" in result
    assert "Speaker 1: Здравствуй" in result

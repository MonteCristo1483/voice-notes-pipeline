"""Pipeline orchestration: media file -> transcript -> note."""

from __future__ import annotations

import logging
import urllib.request
from pathlib import Path

from .config import Settings
from .notes import write_note
from .summarize import summarize
from .transcribe import TooShortError, transcribe

log = logging.getLogger(__name__)


def ollama_available(settings: Settings) -> bool:
    try:
        with urllib.request.urlopen(settings.ollama_url + "/api/version", timeout=5):
            return True
    except Exception:
        return False


def process_media(
    settings: Settings,
    media: Path,
    profile: str = "personal",
    allow_short: bool = False,
) -> Path:
    """Run the full cycle and return the created note path."""
    if profile not in settings.vaults:
        raise ValueError(f"unknown profile: {profile}")
    if not settings.cloud_enabled and not ollama_available(settings):
        raise RuntimeError(
            "local LLM is not running. Start Ollama or configure a cloud provider "
            "(LLM_PROVIDER=cloud, LLM_API_KEY=...)."
        )

    media = media.resolve()
    minimum = 0 if allow_short else settings.min_duration_sec
    transcript = transcribe(settings, media, min_seconds=minimum)
    if not transcript.strip():
        raise RuntimeError("transcript is empty")

    body_title, body = summarize(settings, transcript, profile, fallback_title=media.stem)
    note_path = write_note(
        settings,
        title=body_title,
        body=body,
        transcript=transcript,
        media_file=media,
        profile=profile,
    )
    log.info("note written: %s", note_path)
    return note_path


__all__ = ["TooShortError", "process_media", "ollama_available"]

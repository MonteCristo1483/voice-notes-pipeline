"""Note rendering and writing to the Obsidian vault."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from .config import Settings

INVALID_FILENAME = re.compile(r'[<>:"/\\|?*]')


def safe_filename(name: str) -> str:
    return INVALID_FILENAME.sub("_", name).strip() or "transcript"


def note_datetime(media_file: Path) -> datetime:
    """Recording date: from the filename (OBS) or the file modification time."""
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})[ _](\d{2})-(\d{2})-(\d{2})", media_file.name)
    if match:
        try:
            return datetime(*map(int, match.groups()))
        except ValueError:
            pass
    return datetime.fromtimestamp(os.path.getmtime(media_file))


def write_note(
    settings: Settings,
    title: str,
    body: str,
    transcript: str,
    media_file: Path,
    profile: str,
) -> Path:
    """Write the Markdown note and return its path.

    The file name and the H1 come from the model-generated topic title. The
    header keeps only the recording date — no source path or word count.
    """
    notes_dir = settings.vaults[profile] / "AI" / "Транскрипты"
    notes_dir.mkdir(parents=True, exist_ok=True)

    filename = safe_filename(title)
    path = notes_dir / f"{filename}.md"
    counter = 2
    while path.exists():
        path = notes_dir / f"{filename} ({counter}).md"
        counter += 1

    recorded_at = note_datetime(media_file).strftime("%Y-%m-%d %H:%M")
    note = (
        f"# {title}\n\n"
        f"**Дата:** {recorded_at}\n\n"
        f"{body}\n\n"
        f"---\n\n"
        f"<details><summary>Полный транскрипт</summary>\n\n{transcript}\n\n</details>\n"
    )
    path.write_text(note, encoding="utf-8")
    return path

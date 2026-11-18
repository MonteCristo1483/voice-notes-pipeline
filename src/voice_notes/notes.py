"""Note rendering and writing to the Obsidian vault."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .config import Settings

INVALID_FILENAME = re.compile(r'[<>:"/\\|?*]')


def safe_filename(name: str) -> str:
    return INVALID_FILENAME.sub("_", name).strip() or "transcript"


def write_note(
    settings: Settings,
    base_name: str,
    body: str,
    transcript: str,
    media_file: Path,
    profile: str,
) -> Path:
    """Write the Markdown note and return its path.

    The note contains a small header, the generated body, and the full
    transcript inside a collapsed <details> block for reference.
    """
    notes_dir = settings.vaults[profile] / "AI" / "Транскрипты"
    notes_dir.mkdir(parents=True, exist_ok=True)

    title = safe_filename(base_name)
    path = notes_dir / f"{title}.md"
    counter = 2
    while path.exists():
        path = notes_dir / f"{title} ({counter}).md"
        counter += 1

    processed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    words = len(transcript.split())
    note = (
        f"# {base_name}\n\n"
        f"**Дата обработки:** {processed_at}  \n"
        f"**Источник:** `{media_file.name}`  \n"
        f"**Объём транскрипта:** ~{words} слов\n\n"
        f"{body}\n\n"
        f"---\n\n"
        f"<details><summary>Полный транскрипт</summary>\n\n{transcript}\n\n</details>\n"
    )
    path.write_text(note, encoding="utf-8")
    return path

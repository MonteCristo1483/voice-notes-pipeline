"""Inbox watcher: new media file -> pipeline -> note.

Files are only processed when their size stops changing. Successful ones move
to ``processed/YYYY-MM``, too-short ones to ``skipped/``, and failures to
``quarantine/`` so a broken file cannot cause an endless retry loop.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import shutil
import time
import traceback
from datetime import datetime
from pathlib import Path

from .config import Settings, load_settings
from .errors import TooShortError
from .pipeline import process_media

log = logging.getLogger(__name__)

MEDIA_EXT = {
    ".mp3", ".m4a", ".wav", ".ogg", ".flac", ".wma", ".aac",
    ".mp4", ".mkv", ".webm", ".mov", ".avi", ".ts",
}
SKIP_EXT = {".part", ".tmp", ".crdownload", ".download", ".partial"}


def file_sha1(path: Path) -> str:
    """Content hash: cloud sync may re-upload a file that was already handled."""
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_seen(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_seen(path: Path, data: dict[str, dict[str, str]]) -> None:
    with contextlib.suppress(OSError):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


class Watcher:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _move_to(self, source: Path, inbox: Path, folder: str) -> Path:
        target_dir = inbox / folder
        if folder.startswith("processed"):
            target_dir = inbox / "processed" / datetime.now().strftime("%Y-%m")
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / source.name
        counter = 2
        while target.exists():
            target = target_dir / f"{source.stem} ({counter}){source.suffix}"
            counter += 1
        shutil.move(str(source), str(target))
        return target

    def _archive(self, source: Path, inbox: Path) -> Path:
        return self._move_to(source, inbox, "processed")

    def _quarantine(self, source: Path, inbox: Path) -> Path:
        return self._move_to(source, inbox, "quarantine")

    def _skip_short(self, source: Path, inbox: Path) -> Path:
        return self._move_to(source, inbox, "skipped")

    def _is_stable(self, path: Path) -> bool:
        try:
            last = path.stat().st_size
        except OSError:
            return False
        for _ in range(self.settings.stable_checks):
            time.sleep(self.settings.stable_delay_sec)
            try:
                current = path.stat().st_size
            except OSError:
                return False
            if current != last:
                return False
            last = current
        return True

    def run_once(self) -> None:
        for inbox, profile in self.settings.inboxes.items():
            if not inbox.is_dir():
                continue
            for path in sorted(inbox.iterdir()):
                if not path.is_file():
                    continue
                suffix = path.suffix.lower()
                if suffix in SKIP_EXT or suffix not in MEDIA_EXT:
                    continue

                min_age = (
                    self.settings.min_file_age_personal
                    if profile == "personal"
                    else self.settings.min_file_age_work
                )
                try:
                    age = time.time() - path.stat().st_mtime
                except OSError:
                    continue
                if age < min_age:
                    # Cloud sync may still be writing the file in parts.
                    continue

                log.info("new file (%s): %s — checking it is complete", profile, path.name)
                if not self._is_stable(path):
                    log.info("file still being copied, skipping: %s", path.name)
                    continue

                digest = file_sha1(path)
                seen = load_seen(self.settings.seen_file)
                if digest in seen:
                    destination = self._skip_short(path, inbox)
                    log.info(
                        "already handled (%s), skipping: %s -> %s",
                        seen[digest].get("name", "?"), path.name, destination,
                    )
                    continue

                log.info("processing: %s", path.name)
                try:
                    note = process_media(self.settings, path, profile)
                    self._archive(path, inbox)
                    log.info("done: %s", note)
                    status = "processed"
                except TooShortError as exc:
                    destination = self._skip_short(path, inbox)
                    log.info("skipped (too short): %s — %s -> %s", path.name, exc, destination)
                    status = "skipped"
                except Exception as exc:  # noqa: BLE001 - watcher must survive
                    destination = self._quarantine(path, inbox)
                    log.error("failed: %s — %s -> %s", path.name, exc, destination)
                    traceback.print_exc()
                    status = "quarantined"

                seen[digest] = {
                    "name": path.name,
                    "status": status,
                    "at": datetime.now().isoformat(timespec="seconds"),
                }
                save_seen(self.settings.seen_file, seen)

    def run_forever(self) -> None:
        log.info("watcher started")
        for inbox, profile in self.settings.inboxes.items():
            inbox.mkdir(parents=True, exist_ok=True)
            log.info("watching %s (profile %s)", inbox, profile)
        while True:
            try:
                self.run_once()
            except Exception as exc:  # noqa: BLE001 - keep the loop alive
                log.error("watcher cycle failed: %s", exc)
            time.sleep(self.settings.poll_sec)


def setup_logging(settings: Settings) -> None:
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def main() -> None:
    settings = load_settings()
    setup_logging(settings)
    Watcher(settings).run_forever()


if __name__ == "__main__":
    main()

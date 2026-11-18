"""Command-line entry point: process a single media file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_settings
from .errors import TooShortError
from .pipeline import process_media
from .watcher import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voice-notes",
        description="Transcribe a recording and create an Obsidian note.",
    )
    parser.add_argument("media", type=Path, help="audio or video file")
    parser.add_argument(
        "--profile", choices=["personal", "work"], default="personal",
        help="note template (default: personal)",
    )
    parser.add_argument(
        "--allow-short", action="store_true",
        help="process recordings shorter than MIN_DURATION_SEC",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    setup_logging(settings)

    media = args.media
    if not media.exists():
        print(f"file not found: {media}", file=sys.stderr)
        return 1

    try:
        note = process_media(settings, media, args.profile, args.allow_short)
    except TooShortError as exc:
        print(f"skipped: {exc}")
        print("use --allow-short to process it anyway")
        return 2
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"\ndone. note created:\n{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

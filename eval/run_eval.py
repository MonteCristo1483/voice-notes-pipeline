"""Quality harness: run summarization on synthetic fixtures.

Usage:
    python eval/run_eval.py [case ...]

Results are written to eval/out/<case>.md so prompts and models can be compared
without touching a real vault. No audio is involved; only text leaves the
machine when a cloud provider is configured.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voice_notes.config import load_settings  # noqa: E402
from voice_notes.summarize import summarize  # noqa: E402
from voice_notes.watcher import setup_logging  # noqa: E402

FIXTURES = PROJECT_ROOT / "eval" / "fixtures"
OUT = PROJECT_ROOT / "eval" / "out"

CASES = {
    "meeting": ("meeting.txt", "work"),
    "idea": ("idea.txt", "personal"),
    "long_dialog": ("long_dialog.txt", "personal"),
}


def main(argv: list[str]) -> int:
    wanted = argv or list(CASES)
    unknown = [name for name in wanted if name not in CASES]
    if unknown:
        print("unknown cases:", ", ".join(unknown))
        return 1

    settings = load_settings()
    setup_logging(settings)
    OUT.mkdir(parents=True, exist_ok=True)

    for name in wanted:
        filename, profile = CASES[name]
        transcript = (FIXTURES / filename).read_text(encoding="utf-8")
        print(f"\n=== {name} ({profile}, {len(transcript)} chars) ===")
        note = summarize(settings, transcript, profile)
        target = OUT / f"{name}.md"
        target.write_text(note + "\n", encoding="utf-8")
        print(f"-> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

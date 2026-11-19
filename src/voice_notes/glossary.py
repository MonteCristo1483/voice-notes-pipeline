"""Domain glossary for ASR artifacts.

A JSON file maps regular expressions to canonical terms, for example::

    {"\\bяпур\\w*": "ЕПУР", "\\bepur\\w*": "ЕПУР"}

Patterns are case-insensitive. Applied to the transcript before summarization
and before it is stored in the note.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

Rules = list[tuple[re.Pattern[str], str]]


def load_glossary(path: Path) -> Rules:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        log.warning("cannot read glossary %s: %s", path, exc)
        return []

    rules: Rules = []
    for pattern, replacement in data.items():
        try:
            rules.append((re.compile(pattern, re.IGNORECASE), str(replacement)))
        except re.error as exc:
            log.warning("invalid glossary pattern %r: %s", pattern, exc)
    return rules


def apply_glossary(text: str, rules: Rules) -> str:
    for regex, replacement in rules:
        text = regex.sub(replacement, text)
    return text

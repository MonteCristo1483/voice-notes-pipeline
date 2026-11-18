"""Summarization: transcript -> structured fields -> Markdown note."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from . import prompts
from .config import Settings
from .providers import generate_json
from .render import render_personal_long, render_personal_short, render_work
from .schemas import (
    PERSONAL_EXTRACT_SCHEMA,
    PERSONAL_LONG_SCHEMA,
    PERSONAL_SHORT_SCHEMA,
    WORK_EXTRACT_SCHEMA,
    WORK_SCHEMA,
)
from .transcribe import normalize_speakers

log = logging.getLogger(__name__)


def split_chunks(text: str, size: int = 6000, overlap: int = 800) -> list[str]:
    """Split long transcripts on paragraph boundaries with a small overlap."""
    paragraphs = re.split(r"\n+", text)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 > size and current:
            chunks.append(current)
            current = current[-overlap:] + "\n" + paragraph
        else:
            current = (current + "\n" + paragraph).strip()
    if current:
        chunks.append(current)
    return chunks


def _extract_chunks(
    settings: Settings,
    chunks: list[str],
    template: str,
    schema: dict[str, Any],
    system: str,
) -> list[dict[str, Any]]:
    parts = []
    for index, chunk in enumerate(chunks, 1):
        log.info("chunk %s/%s", index, len(chunks))
        prompt = template.format(index=index, total=len(chunks)) + chunk
        parts.append(generate_json(settings, prompt, schema, system, 0.2))
    return parts


def _reduce(
    settings: Settings,
    parts: list[dict[str, Any]],
    schema: dict[str, Any],
    system: str,
    instruction: str,
) -> dict[str, Any]:
    """Merge chunk summaries in batches so the context never overflows."""
    cloud = settings.cloud_enabled
    max_batch = 20 if cloud else 6
    max_chars = settings.cloud_merge_chars if cloud else settings.merge_batch_chars

    while len(parts) > 1:
        batches: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        size = 0
        for part in parts:
            part_size = len(json.dumps(part, ensure_ascii=False))
            if current and (len(current) >= max_batch or size + part_size > max_chars):
                batches.append(current)
                current, size = [], 0
            current.append(part)
            size += part_size
        if current:
            batches.append(current)
        if len(batches) == len(parts):  # nothing merged — force a pair
            batches = [parts[:2]] + [[part] for part in parts[2:]]

        merged = []
        for index, batch in enumerate(batches, 1):
            if len(batch) == 1:
                merged.append(batch[0])
                continue
            log.info("merging batch %s/%s (%s summaries)", index, len(batches), len(batch))
            merged.append(
                generate_json(
                    settings,
                    instruction + json.dumps(batch, ensure_ascii=False),
                    schema,
                    system,
                    0.2,
                )
            )
        parts = merged
    return parts[0]


def summarize(settings: Settings, transcript: str, profile: str = "personal") -> str:
    """Produce the note body (without the header/footer added by write_note)."""
    if profile not in prompts.SYSTEM_PROMPTS:
        raise ValueError(f"unknown profile: {profile}")

    system = prompts.SYSTEM_PROMPTS[profile]
    provider = "cloud" if settings.cloud_enabled else "local"
    log.info("Step 3/3: summarizing with %s model (profile %s)", provider, profile)
    text = normalize_speakers(transcript.strip())
    single_limit = settings.cloud_single_limit if settings.cloud_enabled else settings.single_pass_limit

    if profile == "work":
        if len(text) < single_limit:
            return render_work(
                generate_json(settings, prompts.WORK_FIELDS + text, WORK_SCHEMA, system, 0.3)
            )
        chunks = split_chunks(text)
        log.info("long transcript: %s chunks", len(chunks))
        parts = _extract_chunks(settings, chunks, prompts.WORK_CHUNK, WORK_EXTRACT_SCHEMA, system)
        merged = _reduce(settings, parts, WORK_SCHEMA, system, prompts.WORK_MERGE)
        return render_work(merged)

    if len(text) < settings.personal_short_limit:
        return render_personal_short(
            generate_json(settings, prompts.PERSONAL_SHORT_FIELDS + text,
                          PERSONAL_SHORT_SCHEMA, system, 0.4)
        )
    if len(text) < single_limit:
        return render_personal_long(
            generate_json(settings, prompts.PERSONAL_LONG_FIELDS + text,
                          PERSONAL_LONG_SCHEMA, system, 0.4)
        )
    chunks = split_chunks(text)
    log.info("long transcript: %s chunks", len(chunks))
    parts = _extract_chunks(settings, chunks, prompts.PERSONAL_CHUNK, PERSONAL_EXTRACT_SCHEMA, system)
    merged = _reduce(settings, parts, PERSONAL_LONG_SCHEMA, system, prompts.PERSONAL_MERGE)
    return render_personal_long(merged)

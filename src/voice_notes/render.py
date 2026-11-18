"""Deterministic Markdown rendering.

Every note is assembled from validated fields. This is where empty sections
disappear, tags get normalized and stray characters are removed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

CJK = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# Placeholders the model likes to emit when a field is unknown.
GENERIC = {
    "участник", "участники", "участник беседы", "все", "автор", "я", "мы", "ты",
    "не указан", "не указано", "неизвестно", "нет", "нет данных", "нет срока",
    "без срока", "срок не указан", "не задан", "н/д", "-", "—",
}


def strip_cjk(text: str) -> str:
    """Drop CJK characters some models emit despite the Russian instruction."""
    lines, out = text.split("\n"), []
    for line in lines:
        cleaned = CJK.sub("", line)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).rstrip()
        if cleaned.strip("-*># ") or cleaned.startswith(("-", "*")):
            out.append(cleaned)
        elif out and out[-1] != "":
            out.append("")
    return "\n".join(out).strip()


def _one_line(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\s+", " ", strip_cjk(value)).strip()
    return text.strip("-*•— ").strip()


def _is_generic(value: Any) -> bool:
    return _one_line(value).lower().rstrip(".") in GENERIC


def _items(values: Iterable[Any] | None, limit: int = 12) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = _one_line(value) if isinstance(value, str) else ""
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def normalize_tags(values: Iterable[Any] | None, limit: int = 8) -> list[str]:
    result: list[str] = []
    for value in values or []:
        tag = _one_line(value).lstrip("#").strip()
        tag = re.sub(r"[^\w\-]+", "_", tag, flags=re.UNICODE).strip("_").lower()
        if tag and f"#{tag}" not in result:
            result.append(f"#{tag}")
        if len(result) >= limit:
            break
    return result


def _bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _tasks_md(tasks: Iterable[Any] | None, limit: int = 12) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for task in tasks or []:
        if isinstance(task, dict):
            title = _one_line(task.get("task"))
            owner = "" if _is_generic(task.get("owner")) else _one_line(task.get("owner"))
            due = "" if _is_generic(task.get("due")) else _one_line(task.get("due"))
        else:
            title, owner, due = _one_line(task), "", ""

        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())

        low = title.lower()
        owner = "" if owner and owner.lower() in low else owner
        due = "" if due and due.lower() in low else due
        tail = f"{owner}, срок: {due}" if owner and due else owner or (f"срок: {due}" if due else "")
        lines.append("- [ ] " + (title + (f" — {tail}" if tail else "")))
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def _decisions_md(decisions: Iterable[Any] | None, limit: int = 10) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for decision in decisions or []:
        if isinstance(decision, dict):
            text = _one_line(decision.get("decision"))
            reason = "" if _is_generic(decision.get("reason")) else _one_line(decision.get("reason"))
        else:
            text, reason = _one_line(decision), ""
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        reason = re.sub(r"^(потому что|так как|из-за того, что)\s+", "", reason, flags=re.I)
        lines.append("- " + text + (f" — {reason}" if reason else ""))
        if len(lines) >= limit:
            break
    return "\n".join(lines)


def _topics_md(topics: Iterable[Any] | None, limit: int = 6) -> str:
    blocks: list[str] = []
    for topic in topics or []:
        if not isinstance(topic, dict):
            continue
        title = _one_line(topic.get("title"))
        points = _items(topic.get("points"), 5)
        if title and points:
            blocks.append(f"### {title}\n" + _bullets(points))
        if len(blocks) >= limit:
            break
    return "\n\n".join(blocks)


def _section(heading: str, content: str) -> str:
    return f"{heading}\n{content}" if content else ""


def _assemble(blocks: Iterable[str], tags: list[str]) -> str:
    body = "\n\n".join(block for block in blocks if block)
    if tags:
        body = body.rstrip() + "\n\n" + " ".join(tags)
    return strip_cjk(body).strip()


def render_personal_short(data: dict[str, Any]) -> str:
    essence = _one_line(data.get("essence"))
    facts = _items(data.get("facts"), 8)
    actions = _items(data.get("actions"), 8)
    return _assemble(
        [
            f"**Суть.** {essence}" if essence else "",
            "**Факты.**\n" + _bullets(facts) if facts else "",
            "**Что сделать.**\n" + _bullets(actions) if actions else "",
        ],
        normalize_tags(data.get("tags"), 6),
    )


def render_personal_long(data: dict[str, Any]) -> str:
    essence = _one_line(data.get("essence"))
    main = _items(data.get("main"), 10)
    actions = _items(data.get("actions"), 8)
    # Bare numbers ("120", "7 тысяч") carry no meaning without context.
    facts = [
        fact for fact in _items(data.get("facts"), 10)
        if not re.fullmatch(r"[\d\s.,%₽€$+\-–—]+", fact)
    ]
    return _assemble(
        [
            _section("## О чём это", essence),
            _section("## Главное", _bullets(main)),
            _section("## Что сделать", _bullets(actions)),
            _section("## Конкретика", _bullets(facts)),
        ],
        normalize_tags(data.get("tags"), 8),
    )


def render_work(data: dict[str, Any]) -> str:
    essence = _one_line(data.get("essence"))
    return _assemble(
        [
            _section("## Суть", essence),
            _section("## Ключевое по темам", _topics_md(data.get("topics"))),
            _section("## Решения и обоснования", _decisions_md(data.get("decisions"))),
            _section("## Задачи", _tasks_md(data.get("tasks"))),
            _section("## Открытые вопросы", _bullets(_items(data.get("questions"), 8))),
            _section("## Термины и факты", _bullets(_items(data.get("facts"), 12))),
            _section("## Материалы", _bullets(_items(data.get("materials"), 10))),
        ],
        normalize_tags(data.get("tags"), 8),
    )

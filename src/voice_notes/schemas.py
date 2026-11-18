"""JSON schemas used for structured model output.

The model fills fields; Markdown is rendered by code. This keeps formatting,
empty sections and tags deterministic instead of hoping the model obeys a
"write clean Markdown" instruction.
"""

from __future__ import annotations

from typing import Any

STRING_LIST: dict[str, Any] = {"type": "array", "items": {"type": "string"}}
DECISION = {
    "type": "object",
    "properties": {"decision": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["decision"],
}
TASK = {
    "type": "object",
    "properties": {
        "task": {"type": "string"},
        "owner": {"type": "string"},
        "due": {"type": "string"},
    },
    "required": ["task"],
}
TOPIC = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "points": STRING_LIST},
    "required": ["title", "points"],
}

WORK_SCHEMA = {
    "type": "object",
    "properties": {
        "essence": {"type": "string"},
        "topics": {"type": "array", "items": TOPIC},
        "decisions": {"type": "array", "items": DECISION},
        "tasks": {"type": "array", "items": TASK},
        "questions": STRING_LIST,
        "facts": STRING_LIST,
        "materials": STRING_LIST,
        "tags": STRING_LIST,
    },
    "required": ["essence", "topics", "decisions", "tasks", "questions", "facts",
                 "materials", "tags"],
}

WORK_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": WORK_SCHEMA["properties"]["topics"],
        "decisions": WORK_SCHEMA["properties"]["decisions"],
        "tasks": WORK_SCHEMA["properties"]["tasks"],
        "questions": STRING_LIST,
        "facts": STRING_LIST,
        "materials": STRING_LIST,
    },
    "required": ["topics", "decisions", "tasks", "questions", "facts", "materials"],
}

PERSONAL_SHORT_SCHEMA = {
    "type": "object",
    "properties": {
        "essence": {"type": "string"},
        "facts": STRING_LIST,
        "actions": STRING_LIST,
        "tags": STRING_LIST,
    },
    "required": ["essence", "facts", "actions", "tags"],
}

PERSONAL_LONG_SCHEMA = {
    "type": "object",
    "properties": {
        "essence": {"type": "string"},
        "main": STRING_LIST,
        "actions": STRING_LIST,
        "facts": STRING_LIST,
        "tags": STRING_LIST,
    },
    "required": ["essence", "main", "actions", "facts", "tags"],
}

PERSONAL_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {"main": STRING_LIST, "facts": STRING_LIST},
    "required": ["main", "facts"],
}


def schema_example(schema: dict[str, Any]) -> Any:
    """Build a JSON skeleton from a schema — a hint for cloud models."""
    kind = schema.get("type")
    if kind == "object":
        return {key: schema_example(value) for key, value in schema.get("properties", {}).items()}
    if kind == "array":
        return [schema_example(schema.get("items", {}))]
    return ""

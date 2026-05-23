#!/usr/bin/env python3
"""Serialization helpers for swarm runtime payloads."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from typing import Any, Dict


def to_jsonable(value: Any) -> Any:
    """Convert common Python objects into JSON-compatible structures."""
    if dataclasses.is_dataclass(value):
        return to_jsonable(dataclasses.asdict(value))

    if isinstance(value, Mapping):
        return {str(k): to_jsonable(v) for k, v in value.items()}

    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]

    if isinstance(value, list):
        return [to_jsonable(v) for v in value]

    if isinstance(value, set):
        return sorted(to_jsonable(v) for v in value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return repr(value)


def json_dumps(obj: Any) -> str:
    """Serialize object to compact deterministic JSON."""
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def json_loads_dict(text: str | bytes | None) -> Dict[str, Any]:
    """Parse JSON object safely, returning {} on failure/non-object."""
    if text is None:
        return {}

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}

    return dict(parsed) if isinstance(parsed, Mapping) else {}


def compact_repr(value: Any, *, limit: int = 500) -> str:
    """Return a compact bounded repr for logs/events."""
    text = repr(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def summarize_value(value: Any, *, max_keys: int = 50) -> Dict[str, Any]:
    """Build a small serializable summary for arbitrary values."""
    if isinstance(value, Mapping):
        return {
            "type": "mapping",
            "keys": [str(k) for k in list(value.keys())[:max_keys]],
            "size": len(value),
        }

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {
            "type": "sequence",
            "size": len(value),
        }

    return {
        "type": type(value).__name__,
        "repr": compact_repr(value),
    }

def json_loads_safe(text: str) -> Dict[str, Any]:
    """Parse JSON object safely, returning empty dict on failure."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}
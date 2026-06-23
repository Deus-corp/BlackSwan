"""Shared validation and normalisation utilities for swarm protocols."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def clean_required(value: Any, field_name: str) -> str:
    """Return a non‑empty, stripped string or raise ValueError."""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def optional_str(value: Any) -> str | None:
    """Return a stripped string or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def safe_dict(value: Any) -> dict[str, Any]:
    """Return the value as a dict if it is a Mapping, otherwise an empty dict."""
    return dict(value) if isinstance(value, Mapping) else {}


def safe_float(value: Any, default: float) -> float:
    """Return the value as a float, or *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int) -> int:
    """Return the value as an int, or *default* on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_ttl(value: Any) -> int | None:
    """Return a positive int or None from a TTL value."""
    if value is None:
        return None
    try:
        ttl = int(value)
    except (TypeError, ValueError):
        return None
    return ttl if ttl > 0 else None


def clamp_confidence(value: Any) -> float:
    """Clamp a confidence value to [0.0, 1.0]."""
    number = safe_float(value, 0.0)
    return max(0.0, min(1.0, number))


def safe_str_list(value: Any) -> list[str]:
    """Return a list of non‑empty strings from an iterable."""
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def safe_items(value: Any) -> list[dict[str, Any]]:
    """Return a list of dicts from an iterable of Mappings."""
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, Mapping)):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            items.append(dict(item))
    return items
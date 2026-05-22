"""Utility helpers for security meta-agent logic."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict


def now_ts() -> int:
    return int(time.time())


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def normalize_action(action: Any) -> str:
    return str(action or "MAINTAIN").strip().upper()


def strip_to_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}
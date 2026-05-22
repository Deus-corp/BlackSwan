#!/usr/bin/env python3
"""Thin façade for the shared security runtime.

This module serves as a central utility layer for security-related operations,
providing common schemas, environment parsing, and event orchestration.
"""

from __future__ import annotations

import json
import os
import time
import uuid
import hashlib
from typing import Any, Dict, List, Optional

from src.swarms.security.memory import (
    SecurityCommand,
    SecurityEvent,
    SecurityEventType,
)

# Emergency flush setting configuration constants
# SEC_ALLOW_EMERGENCY_FLUSH_INPUT defaults to False for safety.

def now_ts() -> int:
    """Return the current unix timestamp as an integer."""
    return int(time.time())


def new_gid(prefix: str) -> str:
    """Generate a unique global identifier with a specific prefix."""
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


def prompt_hash(text: str) -> str:
    """Return a SHA-256 hash of the provided input string."""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def json_dumps(obj: Any) -> str:
    """Serialize an object to a JSON string without ASCII escaping."""
    return json.dumps(obj, ensure_ascii=False)


def json_loads_safe(text: str) -> Dict[str, Any]:
    """Safely parse a JSON string, returning an empty dict on failure."""
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def parse_json_loose(text: str) -> Dict[str, Any]:
    """Attempt to extract and parse JSON from a potentially malformed string."""
    cleaned = text.strip()
    try:
        return json.loads(cleaned) if isinstance(json.loads(cleaned), dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass
    
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            content = cleaned[start : end + 1]
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def split_csv(env_name: str) -> List[str]:
    """Retrieve a comma-separated list from environment variables."""
    raw = os.environ.get(env_name, "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def get_bool(env_name: str, default: bool) -> bool:
    """Retrieve a boolean flag from an environment variable."""
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_int(env_name: str, default: int) -> int:
    """Retrieve an integer from an environment variable, defaulting on error."""
    try:
        return int(os.environ.get(env_name, str(default)))
    except (ValueError, TypeError):
        return default


def make_security_event(
    *,
    event_type: SecurityEventType,
    source_gid: str,
    parent_gid: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
    gid_prefix: str = "sec_evt",
) -> SecurityEvent:
    """Construct a standardized security event dictionary."""
    return {
        "type": "security_event",
        "event_type": event_type,
        "gid": new_gid(gid_prefix),
        "source_gid": source_gid,
        "parent_gid": parent_gid,
        "timestamp": float(time.time()),
        "provenance": provenance or {},
        "data": data or {},
    }


def make_security_command(
    *,
    action: str,
    source_gid: str,
    parent_gid: Optional[str] = None,
    expires_at: Optional[int] = None,
    data: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> SecurityCommand:
    """Construct a standardized security command dictionary."""
    now = now_ts()
    return {
        "type": "sec_command",
        "event_type": "command_issued",
        "gid": new_gid("sec_cmd"),
        "source_gid": source_gid,
        "parent_gid": parent_gid,
        "timestamp": float(time.time()),
        "expires_at": expires_at or (now + 600),
        "provenance": provenance or {},
        "data": {"action": action, **(data or {})},
    }
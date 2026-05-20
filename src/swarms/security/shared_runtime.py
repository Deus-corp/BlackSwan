#!/usr/bin/env python3
"""Thin façade for the shared security runtime.

This module intentionally stays small and re-exports the shared memory,
policy, event schema, and firewall helper.
"""

## Emergency flush setting
### The dangerous capability remains present but locked by default:
### `SEC_ALLOW_EMERGENCY_FLUSH_INPUT=false` by default
### enable only after you test it explicitly

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict
from urllib.parse import urlparse

from src.swarms.security.memory import (
    FirewallPolicy,
    SecurityPolicy,
    SecurityCommand,
    SecurityEvent,
    SecurityEventType,
    SecurityMemory,
    command_exists,
    extract_domain,
    new_gid,
)
from src.swarms.security.firewall import FirewallManager


def now_ts() -> int:
    return int(time.time())


def new_gid(prefix: str) -> str:
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}"


def prompt_hash(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def json_loads_safe(text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def parse_json_loose(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def split_csv(env_name: str) -> List[str]:
    raw = os.environ.get(env_name, "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def get_bool(env_name: str, default: bool) -> bool:
    raw = os.environ.get(env_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_int(env_name: str, default: int) -> int:
    try:
        return int(os.environ.get(env_name, str(default)))
    except Exception:
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
    gid = new_gid(gid_prefix)
    return {
        "type": "security_event",
        "event_type": event_type,
        "gid": gid,
        "source_gid": source_gid,
        "parent_gid": parent_gid,
        "timestamp": time.time(),
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
    now = now_ts()
    return {
        "type": "sec_command",
        "event_type": "command_issued",
        "gid": new_gid("sec_cmd"),
        "source_gid": source_gid,
        "parent_gid": parent_gid,
        "timestamp": time.time(),
        "expires_at": expires_at or (now + 600),
        "provenance": provenance or {},
        "data": {"action": action, **(data or {})},
    }
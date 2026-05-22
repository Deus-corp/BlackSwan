#!/usr/bin/env python3
"""Shared security runtime helpers."""

from __future__ import annotations

import hashlib
import json
import time

from typing import Any, Dict, Optional

from .memory import (
    FirewallPolicy,
    SecurityPolicy,
    SecurityCommand,
    SecurityEvent,
    SecurityEventType,
    SecurityMemory,
    command_exists,
    extract_domain,
    new_gid,
    now_ts,
)


def prompt_hash(text: str) -> str:
    return hashlib.sha256(
        text.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()


def json_dumps(obj: Any) -> str:
    return json.dumps(
        obj,
        ensure_ascii=False,
    )


def json_loads_safe(text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except Exception:
        pass

    return {}


def parse_json_loose(text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass

    return {}


def make_security_event(
    *,
    event_type: SecurityEventType,
    source_gid: str,
    parent_gid: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    provenance: Optional[Dict[str, Any]] = None,
) -> SecurityEvent:

    return {
        "type": "security_event",
        "event_type": event_type,
        "gid": new_gid("sec_evt"),
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

    return {
        "type": "sec_command",
        "event_type": "command_issued",
        "gid": new_gid("sec_cmd"),
        "source_gid": source_gid,
        "parent_gid": parent_gid,
        "timestamp": float(time.time()),
        "expires_at": expires_at or (now_ts() + 600),
        "provenance": provenance or {},
        "data": {
            "action": action,
            **(data or {}),
        },
    }
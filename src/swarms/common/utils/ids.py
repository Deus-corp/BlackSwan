#!/usr/bin/env python3
"""ID utilities for swarm runtime objects."""

from __future__ import annotations

import uuid
from typing import Optional


def new_gid(prefix: str = "gid", *, namespace: Optional[str] = None) -> str:
    """Create a globally unique id with an optional namespace.

    Examples:
        new_gid("hb", namespace="security") -> security_hb_ab12...
        new_gid("cmd") -> cmd_ab12...
    """
    clean_prefix = _clean_part(prefix or "gid")
    clean_namespace = _clean_part(namespace) if namespace else ""

    if clean_namespace:
        return f"{clean_namespace}_{clean_prefix}_{uuid.uuid4().hex}"

    return f"{clean_prefix}_{uuid.uuid4().hex}"


def new_short_id(prefix: str = "id", *, size: int = 8) -> str:
    """Create a short non-cryptographic id for runtime identities."""
    clean_prefix = _clean_part(prefix or "id")
    size = max(4, min(int(size), 32))
    return f"{clean_prefix}-{uuid.uuid4().hex[:size]}"


def new_node_id(swarm_type: str, *, role: str = "node") -> str:
    """Create a standard node id."""
    swarm = _clean_part(swarm_type or "swarm")
    role_part = _clean_part(role or "node")
    return new_short_id(f"{swarm}-{role_part}")


def new_meta_agent_id(swarm_type: str) -> str:
    """Create a standard meta-agent id."""
    swarm = _clean_part(swarm_type or "swarm")
    return new_short_id(f"{swarm}-meta")


def new_overseer_id() -> str:
    """Create a standard overseer id."""
    return new_short_id("overseer")


def _clean_part(value: str | None) -> str:
    """Normalize id fragments into stable snake-ish tokens."""
    if not value:
        return "id"

    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value).strip().lower())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "id"
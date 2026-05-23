"""Common swarm protocol helpers."""

from __future__ import annotations

from .commands import (
    command_action,
    command_fingerprint,
    command_is_expired,
    command_targets,
    make_swarm_command,
    normalize_command,
    normalize_commands,
)
from .events import (
    make_swarm_event,
    normalize_event,
    normalize_events,
)
from .heartbeats import (
    make_swarm_heartbeat,
    normalize_heartbeat,
    normalize_heartbeats,
)
from .topology import (
    EXPLORER_COMMANDS,
    IMPROVER_COMMANDS,
    OVERSEER_COMMANDS,
    SECURITY_COMMANDS,
    SWARM_TOPOLOGY,
    TRADE_COMMANDS,
    SwarmRoleSpec,
    SwarmSpec,
    command_allowed_for_swarm,
    command_requires_explicit_gate,
    get_role_spec,
    get_swarm_spec,
    is_advisory_role,
    is_advisory_swarm,
    is_known_role,
    is_known_swarm,
    known_roles,
    known_swarms,
)

__all__ = [
    "EXPLORER_COMMANDS",
    "IMPROVER_COMMANDS",
    "OVERSEER_COMMANDS",
    "SECURITY_COMMANDS",
    "SWARM_TOPOLOGY",
    "TRADE_COMMANDS",
    "SwarmRoleSpec",
    "SwarmSpec",
    "command_action",
    "command_allowed_for_swarm",
    "command_is_expired",
    "command_requires_explicit_gate",
    "command_targets",
    "get_role_spec",
    "get_swarm_spec",
    "is_advisory_role",
    "is_advisory_swarm",
    "is_known_role",
    "is_known_swarm",
    "known_roles",
    "known_swarms",
    "make_swarm_command",
    "make_swarm_event",
    "make_swarm_heartbeat",
    "normalize_command",
    "normalize_commands",
    "normalize_event",
    "normalize_events",
    "normalize_heartbeat",
    "normalize_heartbeats",
    "command_fingerprint",
]
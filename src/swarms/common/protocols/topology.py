"""Canonical swarm topology definitions.

This module is the shared source of truth for:
- known swarm types
- known roles
- allowed command targets
- direct vs advisory control
- legacy compatibility notes

It intentionally contains static metadata only. Runtime state still lives in
CRDT heartbeats/events/commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Mapping, Optional, Tuple


@dataclass(frozen=True, slots=True)
class SwarmRoleSpec:
    """Role-level topology metadata."""

    role: str
    description: str
    can_receive_commands: bool = True
    advisory_only: bool = False


@dataclass(frozen=True, slots=True)
class SwarmSpec:
    """Swarm-level topology metadata."""

    swarm_type: str
    description: str
    roles: Mapping[str, SwarmRoleSpec]
    managed_by_overseer: bool = True
    advisory_only: bool = False
    legacy_command_types: Tuple[str, ...] = field(default_factory=tuple)
    canonical_command_types: FrozenSet[str] = field(default_factory=frozenset)


SECURITY_COMMANDS: FrozenSet[str] = frozenset(
    {
        "UNBLOCK_ALL",
        "PARTIAL_UNBLOCK",
        "EMERGENCY_FLUSH_INPUT",
        "RESTART_NODE",
        "PAUSE",
        "RESUME",
    }
)

EXPLORER_COMMANDS: FrozenSet[str] = frozenset(
    {
        "PAUSE",
        "RESUME",
        "RESTART_NODE",
        "ADD_TARGETS",
        "EXPLORE_URLS",
    }
)

IMPROVER_COMMANDS: FrozenSet[str] = frozenset(
    {
        "PAUSE",
        "RESUME",
        "RUN_ONCE",
        "GENERATE_PROPOSALS",
        "SET_PROPOSALS",
        "SET_SINGLE_PASS",
        "RESTART_NODE",
    }
)

TRADE_COMMANDS: FrozenSet[str] = frozenset(
    {
        "ADJUST_SWARM",
        "REDUCE_RISK",
        "INCREASE_EXPLORATION",
        "RESTART_NODE",
        "PAUSE",
        "RESUME",
    }
)

OVERSEER_COMMANDS: FrozenSet[str] = frozenset(
    {
        "PAUSE",
        "RESUME",
        "RESTART_NODE",
        "RELOAD_POLICY",
    }
)


SWARM_TOPOLOGY: Dict[str, SwarmSpec] = {
    "security": SwarmSpec(
        swarm_type="security",
        description="Defensive security swarm for firewall, incidents, and vulnerability signals.",
        managed_by_overseer=True,
        advisory_only=False,
        legacy_command_types=("sec_command",),
        canonical_command_types=SECURITY_COMMANDS,
        roles={
            "node": SwarmRoleSpec(
                role="node",
                description="Security worker node applying local defensive commands.",
                can_receive_commands=True,
                advisory_only=False,
            ),
            "meta_agent": SwarmRoleSpec(
                role="meta_agent",
                description="Security coordinator/meta-agent evaluating security posture.",
                can_receive_commands=True,
                advisory_only=False,
            ),
        },
    ),
    "explorer": SwarmSpec(
        swarm_type="explorer",
        description="Exploration swarm for discovering, fetching, and classifying external signals.",
        managed_by_overseer=True,
        advisory_only=False,
        legacy_command_types=("explorer_command", "explorer_targets"),
        canonical_command_types=EXPLORER_COMMANDS,
        roles={
            "node": SwarmRoleSpec(
                role="node",
                description="Explorer worker node consuming targets and emitting findings.",
                can_receive_commands=True,
                advisory_only=False,
            ),
            "meta_agent": SwarmRoleSpec(
                role="meta_agent",
                description="Explorer meta-agent classifying findings and suggesting new targets.",
                can_receive_commands=True,
                advisory_only=False,
            ),
        },
    ),
    "improver": SwarmSpec(
        swarm_type="improver",
        description="Maintenance/code-improvement swarm for offline project improvement.",
        managed_by_overseer=True,
        advisory_only=True,
        legacy_command_types=("improver_heartbeat",),
        canonical_command_types=IMPROVER_COMMANDS,
        roles={
            "maintenance_agent": SwarmRoleSpec(
                role="maintenance_agent",
                description="Code improvement maintenance agent.",
                can_receive_commands=True,
                advisory_only=True,
            ),
        },
    ),
    "trade": SwarmSpec(
        swarm_type="trade",
        description="Trading swarm for market execution, evolution, and risk-aware trading.",
        managed_by_overseer=True,
        advisory_only=False,
        legacy_command_types=("meta_command_json", "trade_command"),
        canonical_command_types=TRADE_COMMANDS,
        roles={
            "node": SwarmRoleSpec(
                role="node",
                description="Trade worker node.",
                can_receive_commands=True,
                advisory_only=False,
            ),
            "meta_agent": SwarmRoleSpec(
                role="meta_agent",
                description="Trade coordinator/meta-agent.",
                can_receive_commands=True,
                advisory_only=False,
            ),
        },
    ),
    "overseer": SwarmSpec(
        swarm_type="overseer",
        description="Global orchestration layer above swarm ecosystems.",
        managed_by_overseer=False,
        advisory_only=False,
        legacy_command_types=("overseer_heartbeat",),
        canonical_command_types=OVERSEER_COMMANDS,
        roles={
            "overseer": SwarmRoleSpec(
                role="overseer",
                description="Global orchestrator.",
                can_receive_commands=True,
                advisory_only=False,
            ),
        },
    ),
}


def get_swarm_spec(swarm_type: str) -> Optional[SwarmSpec]:
    """Return topology spec for swarm type."""
    return SWARM_TOPOLOGY.get(str(swarm_type))


def get_role_spec(swarm_type: str, role: str) -> Optional[SwarmRoleSpec]:
    """Return role spec for swarm type + role."""
    spec = get_swarm_spec(swarm_type)
    if spec is None:
        return None
    return spec.roles.get(str(role))


def known_swarms() -> Tuple[str, ...]:
    """Return known swarm type names."""
    return tuple(sorted(SWARM_TOPOLOGY.keys()))


def known_roles(swarm_type: str) -> Tuple[str, ...]:
    """Return known roles for a swarm."""
    spec = get_swarm_spec(swarm_type)
    if spec is None:
        return ()
    return tuple(sorted(spec.roles.keys()))


def is_known_swarm(swarm_type: str) -> bool:
    """Whether swarm_type is known."""
    return str(swarm_type) in SWARM_TOPOLOGY


def is_known_role(swarm_type: str, role: str) -> bool:
    """Whether role is known for swarm_type."""
    return get_role_spec(swarm_type, role) is not None


def is_advisory_swarm(swarm_type: str) -> bool:
    """Whether swarm is advisory-only."""
    spec = get_swarm_spec(swarm_type)
    return bool(spec.advisory_only) if spec else False


def is_advisory_role(swarm_type: str, role: str) -> bool:
    """Whether role is advisory-only."""
    role_spec = get_role_spec(swarm_type, role)
    if role_spec is None:
        return False
    return bool(role_spec.advisory_only)


def command_allowed_for_swarm(swarm_type: str, command_type: str) -> bool:
    """Whether command type is known for swarm."""
    spec = get_swarm_spec(swarm_type)
    if spec is None:
        return False
    return str(command_type).upper() in spec.canonical_command_types


def command_requires_explicit_gate(swarm_type: str, role: str, command_type: str) -> bool:
    """Whether a command should require explicit safety gate before execution.

    v1 rule:
        Any command targeting advisory-only swarm/role requires explicit gate.
    """
    if is_advisory_swarm(swarm_type):
        return True
    if is_advisory_role(swarm_type, role):
        return True
    return False
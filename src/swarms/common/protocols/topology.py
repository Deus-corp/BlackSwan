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



SAFE_LOCAL_EXECUTION = "safe_local_execution"
NETWORK_READ = "network_read"
TESTNET_EXTERNAL_WRITE = "testnet_external_write"
EXTERNAL_WRITE_STUB = "external_write_stub"
PRODUCTION_FINANCIAL_WRITE = "production_financial_write"
SYSTEM_DANGEROUS_STUB = "system_dangerous_stub"

DANGEROUS_EXECUTION_RISK_TIERS: FrozenSet[str] = frozenset(
    {
        EXTERNAL_WRITE_STUB,
        PRODUCTION_FINANCIAL_WRITE,
        SYSTEM_DANGEROUS_STUB,
    }
)

DEFAULT_SWARM_RISK_TIERS: Mapping[str, str] = {
    "security": SYSTEM_DANGEROUS_STUB,
    "explorer": NETWORK_READ,
    "improver": SAFE_LOCAL_EXECUTION,
    "trade": TESTNET_EXTERNAL_WRITE,
    "overseer": SAFE_LOCAL_EXECUTION,
    "memory": SAFE_LOCAL_EXECUTION,
    "simulation": SAFE_LOCAL_EXECUTION,
}

COMMAND_RISK_TIERS: Mapping[tuple[str, str], str] = {
    ("security", "PAUSE"): SAFE_LOCAL_EXECUTION,
    ("security", "RESUME"): SAFE_LOCAL_EXECUTION,
    ("security", "RESTART_NODE"): SYSTEM_DANGEROUS_STUB,
    ("security", "UNBLOCK_ALL"): SYSTEM_DANGEROUS_STUB,
    ("security", "PARTIAL_UNBLOCK"): SYSTEM_DANGEROUS_STUB,
    ("security", "EMERGENCY_FLUSH_INPUT"): SYSTEM_DANGEROUS_STUB,

    ("explorer", "PAUSE"): SAFE_LOCAL_EXECUTION,
    ("explorer", "RESUME"): SAFE_LOCAL_EXECUTION,
    ("explorer", "RESTART_NODE"): SYSTEM_DANGEROUS_STUB,
    ("explorer", "ADD_TARGETS"): NETWORK_READ,
    ("explorer", "EXPLORE_URLS"): NETWORK_READ,

    ("trade", "PAUSE"): SAFE_LOCAL_EXECUTION,
    ("trade", "RESUME"): SAFE_LOCAL_EXECUTION,
    ("trade", "RESTART_NODE"): SYSTEM_DANGEROUS_STUB,
    ("trade", "ADJUST_SWARM"): TESTNET_EXTERNAL_WRITE,
    ("trade", "REDUCE_RISK"): TESTNET_EXTERNAL_WRITE,
    ("trade", "INCREASE_EXPLORATION"): TESTNET_EXTERNAL_WRITE,

    ("improver", "PAUSE"): SAFE_LOCAL_EXECUTION,
    ("improver", "RESUME"): SAFE_LOCAL_EXECUTION,
    ("improver", "RESTART_NODE"): SYSTEM_DANGEROUS_STUB,
    ("improver", "RUN_ONCE"): SAFE_LOCAL_EXECUTION,
    ("improver", "GENERATE_PROPOSALS"): SAFE_LOCAL_EXECUTION,
    ("improver", "SET_PROPOSALS"): SAFE_LOCAL_EXECUTION,
    ("improver", "SET_SINGLE_PASS"): SAFE_LOCAL_EXECUTION,

    ("memory", "PAUSE"): SAFE_LOCAL_EXECUTION,
    ("memory", "RESUME"): SAFE_LOCAL_EXECUTION,
    ("memory", "RESTART_NODE"): SYSTEM_DANGEROUS_STUB,
    ("memory", "CONSOLIDATE"): SAFE_LOCAL_EXECUTION,
    ("memory", "EXPORT_GOLD_SAMPLES"): SAFE_LOCAL_EXECUTION,
    ("memory", "REINDEX"): SAFE_LOCAL_EXECUTION,

    ("simulation", "PAUSE"): SAFE_LOCAL_EXECUTION,
    ("simulation", "RESUME"): SAFE_LOCAL_EXECUTION,
    ("simulation", "RESTART_NODE"): SYSTEM_DANGEROUS_STUB,
    ("simulation", "RUN_SCENARIO"): SAFE_LOCAL_EXECUTION,
    ("simulation", "RUN_STRESS_TEST"): SAFE_LOCAL_EXECUTION,
    ("simulation", "EVALUATE_POLICY"): SAFE_LOCAL_EXECUTION,

    ("overseer", "PAUSE"): SAFE_LOCAL_EXECUTION,
    ("overseer", "RESUME"): SAFE_LOCAL_EXECUTION,
    ("overseer", "RESTART_NODE"): SYSTEM_DANGEROUS_STUB,
    ("overseer", "RELOAD_POLICY"): SAFE_LOCAL_EXECUTION,
}


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

MEMORY_COMMANDS: FrozenSet[str] = frozenset(
    {
        "PAUSE",
        "RESUME",
        "RESTART_NODE",
        "CONSOLIDATE",
        "EXPORT_GOLD_SAMPLES",
        "REINDEX",
    }
)

SIMULATION_COMMANDS: FrozenSet[str] = frozenset(
    {
        "PAUSE",
        "RESUME",
        "RESTART_NODE",
        "RUN_SCENARIO",
        "RUN_STRESS_TEST",
        "EVALUATE_POLICY",
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
    "memory": SwarmSpec(
        swarm_type="memory",
        description=(
            "Memory swarm for episodic memory, semantic memory, retrieval, "
            "consolidation, and experience export."
        ),
        managed_by_overseer=True,
        advisory_only=True,
        legacy_command_types=("memory_heartbeat",),
        canonical_command_types=MEMORY_COMMANDS,
        roles={
            "node": SwarmRoleSpec(
                role="node",
                description="Memory worker node publishing memory health and consolidation status.",
                can_receive_commands=True,
                advisory_only=True,
            ),
            "meta_agent": SwarmRoleSpec(
                role="meta_agent",
                description="Memory coordinator/meta-agent for retrieval and consolidation policy.",
                can_receive_commands=True,
                advisory_only=True,
            ),
        },
    ),
    "simulation": SwarmSpec(
        swarm_type="simulation",
        description=(
            "Simulation swarm for offline worlds, counterfactual tests, stress tests, "
            "and policy evaluation before live deployment."
        ),
        managed_by_overseer=True,
        advisory_only=True,
        legacy_command_types=("simulation_heartbeat",),
        canonical_command_types=SIMULATION_COMMANDS,
        roles={
            "node": SwarmRoleSpec(
                role="node",
                description="Simulation worker node running scenarios and publishing evaluation results.",
                can_receive_commands=True,
                advisory_only=True,
            ),
            "meta_agent": SwarmRoleSpec(
                role="meta_agent",
                description="Simulation coordinator/meta-agent for experiment scheduling.",
                can_receive_commands=True,
                advisory_only=True,
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


def command_risk_tier(swarm_type: str, command_type: str) -> str:
    """Return static execution risk tier for a swarm command.

    Unknown commands are treated as system-dangerous by default.
    """
    clean_swarm = str(swarm_type or "").strip()
    clean_command = str(command_type or "").strip().upper()

    if not clean_swarm or not clean_command:
        return SYSTEM_DANGEROUS_STUB

    if not command_allowed_for_swarm(clean_swarm, clean_command):
        return SYSTEM_DANGEROUS_STUB

    return COMMAND_RISK_TIERS.get(
        (clean_swarm, clean_command),
        DEFAULT_SWARM_RISK_TIERS.get(clean_swarm, SYSTEM_DANGEROUS_STUB),
    )


def command_is_dangerous(swarm_type: str, command_type: str) -> bool:
    """Whether a command belongs to a dangerous/stubbed execution tier."""
    return command_risk_tier(swarm_type, command_type) in DANGEROUS_EXECUTION_RISK_TIERS


def command_requires_explicit_gate(swarm_type: str, role: str, command_type: str) -> bool:
    """Whether a command should require explicit advisory safety gate.

    This helper preserves the historical advisory-gate semantics used by
    runtime smoke checks.

    Execution danger is tracked separately through command_risk_tier() and
    command_is_dangerous(). A dangerous command is not automatically an
    advisory-gated command here, because older runtime contracts use this helper
    for advisory swarm/role routing only.
    """
    if is_advisory_swarm(swarm_type):
        return True
    if is_advisory_role(swarm_type, role):
        return True
    return False
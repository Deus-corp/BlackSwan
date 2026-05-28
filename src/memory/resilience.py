"""Memory resilience policy for autonomous multi-swarm memory.

This module defines how a node should choose memory read/write targets under
normal and degraded conditions.

Memory layers:

- local: fast process-local memory, may be volatile.
- own: durable node/swarm-owned memory.
- shared: CRDT/event-backed memory shared between swarms.
- global: consolidated memory managed by the memory swarm.

The policy is intentionally storage-agnostic. It does not perform I/O; it only
decides where to read from and write to depending on component availability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MemoryLayer(str, Enum):
    """Canonical memory layer names."""

    LOCAL = "local"
    OWN = "own"
    SHARED = "shared"
    GLOBAL = "global"


class MemoryAvailability(str, Enum):
    """Availability status for memory infrastructure."""

    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

class MemoryResilienceStatus(str, Enum):
    """High-level memory resilience status."""

    PRIMARY_OK = "primary_ok"
    FALLBACK_ACTIVE = "fallback_active"
    SHARED_BRIDGE_LAGGING = "shared_bridge_lagging"
    DEGRADED = "degraded"
    RECOVERY_NEEDED = "recovery_needed"

@dataclass(frozen=True, slots=True)
class MemoryHealth:
    """Runtime health summary for memory-related infrastructure."""

    local: MemoryAvailability = MemoryAvailability.AVAILABLE
    own: MemoryAvailability = MemoryAvailability.AVAILABLE
    shared: MemoryAvailability = MemoryAvailability.AVAILABLE
    global_memory: MemoryAvailability = MemoryAvailability.AVAILABLE
    memory_swarm_seen: bool = True
    crdt_available: bool = True
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["local"] = self.local.value
        data["own"] = self.own.value
        data["shared"] = self.shared.value
        data["global_memory"] = self.global_memory.value
        return data

    @property
    def is_degraded(self) -> bool:
        """Return True if any important memory layer is degraded/unavailable."""
        return (
            self.local != MemoryAvailability.AVAILABLE
            or self.own != MemoryAvailability.AVAILABLE
            or self.shared != MemoryAvailability.AVAILABLE
            or self.global_memory != MemoryAvailability.AVAILABLE
            or not self.memory_swarm_seen
            or not self.crdt_available
        )

@dataclass(frozen=True, slots=True)
class MemoryResilienceAssessment:
    """Compact resilience assessment suitable for heartbeat/Overseer."""

    status: MemoryResilienceStatus
    degraded: bool = False
    fallback_active: bool = False
    shared_bridge_lagging: bool = False
    recovery_needed: bool = False
    reason: str = "ok"
    total_records: int = 0
    shared_seen_records: int = 0
    shared_accepted_records: int = 0
    shared_rejected_records: int = 0
    shared_skipped_records: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

@dataclass(frozen=True, slots=True)
class MemoryRoutePlan:
    """Resolved memory routing decision."""

    write_targets: tuple[MemoryLayer, ...] = field(default_factory=tuple)
    read_order: tuple[MemoryLayer, ...] = field(default_factory=tuple)
    queue_for_later: bool = False
    degraded: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "write_targets": [layer.value for layer in self.write_targets],
            "read_order": [layer.value for layer in self.read_order],
            "queue_for_later": self.queue_for_later,
            "degraded": self.degraded,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class MemoryResiliencePolicy:
    """Storage-agnostic routing policy for resilient memory operations."""

    write_local: bool = True
    write_own: bool = True
    write_shared: bool = True
    write_global: bool = False
    read_local_first: bool = True
    read_global_last: bool = True

    def choose_write_targets(self, health: MemoryHealth) -> MemoryRoutePlan:
        """Choose write targets based on current memory health."""
        targets: list[MemoryLayer] = []
        reasons: list[str] = []
        queue_for_later = False

        if self.write_local and health.local != MemoryAvailability.UNAVAILABLE:
            targets.append(MemoryLayer.LOCAL)
        else:
            reasons.append("local_unavailable")

        if self.write_own and health.own != MemoryAvailability.UNAVAILABLE:
            targets.append(MemoryLayer.OWN)
        else:
            reasons.append("own_unavailable")

        if (
            self.write_shared
            and health.shared != MemoryAvailability.UNAVAILABLE
            and health.crdt_available
        ):
            targets.append(MemoryLayer.SHARED)
        else:
            if self.write_shared:
                queue_for_later = True
                reasons.append("shared_unavailable_or_crdt_down")

        if (
            self.write_global
            and health.global_memory != MemoryAvailability.UNAVAILABLE
            and health.memory_swarm_seen
        ):
            targets.append(MemoryLayer.GLOBAL)
        elif self.write_global:
            queue_for_later = True
            reasons.append("global_memory_unavailable")

        degraded = health.is_degraded or queue_for_later

        return MemoryRoutePlan(
            write_targets=tuple(targets),
            read_order=(),
            queue_for_later=queue_for_later,
            degraded=degraded,
            reason=";".join(reasons) if reasons else "ok",
        )

    def choose_read_order(self, health: MemoryHealth) -> MemoryRoutePlan:
        """Choose read order based on current memory health."""
        order: list[MemoryLayer] = []

        local_available = health.local != MemoryAvailability.UNAVAILABLE
        own_available = health.own != MemoryAvailability.UNAVAILABLE
        shared_available = (
            health.shared != MemoryAvailability.UNAVAILABLE and health.crdt_available
        )
        global_available = (
            health.global_memory != MemoryAvailability.UNAVAILABLE
            and health.memory_swarm_seen
        )

        if self.read_local_first and local_available:
            order.append(MemoryLayer.LOCAL)

        if own_available:
            order.append(MemoryLayer.OWN)

        if shared_available:
            order.append(MemoryLayer.SHARED)

        if global_available:
            order.append(MemoryLayer.GLOBAL)

        if not self.read_local_first and local_available and MemoryLayer.LOCAL not in order:
            order.insert(0, MemoryLayer.LOCAL)

        if self.read_global_last and MemoryLayer.GLOBAL in order:
            order = [layer for layer in order if layer != MemoryLayer.GLOBAL] + [MemoryLayer.GLOBAL]

        reasons: list[str] = []
        if not health.crdt_available:
            reasons.append("crdt_down")
        if not health.memory_swarm_seen:
            reasons.append("memory_swarm_unseen")
        if not order:
            reasons.append("no_memory_layers_available")

        return MemoryRoutePlan(
            write_targets=(),
            read_order=tuple(order),
            queue_for_later=False,
            degraded=health.is_degraded,
            reason=";".join(reasons) if reasons else "ok",
        )

    def plan(self, health: MemoryHealth) -> dict[str, Any]:
        """Return combined read/write routing plan."""
        write_plan = self.choose_write_targets(health)
        read_plan = self.choose_read_order(health)

        return {
            "health": health.to_dict(),
            "write": write_plan.to_dict(),
            "read": read_plan.to_dict(),
        }
    
def assess_memory_resilience(
    health: MemoryHealth,
    *,
    total_records: int = 0,
    shared_seen_records: int = 0,
    shared_accepted_records: int = 0,
    shared_rejected_records: int = 0,
    shared_skipped_records: int = 0,
) -> MemoryResilienceAssessment:
    """Assess memory resilience from health and shared bridge counters."""
    safe_total = _safe_int(total_records)
    safe_seen = _safe_int(shared_seen_records)
    safe_accepted = _safe_int(shared_accepted_records)
    safe_rejected = _safe_int(shared_rejected_records)
    safe_skipped = _safe_int(shared_skipped_records)

    fallback_active = (
        health.global_memory != MemoryAvailability.AVAILABLE
        or not health.memory_swarm_seen
        or not health.crdt_available
    )

    shared_bridge_lagging = (
        safe_seen > 0
        and safe_accepted == 0
        and safe_skipped >= 25
    )

    recovery_needed = (
        not health.crdt_available
        or health.shared == MemoryAvailability.UNAVAILABLE
        or health.global_memory == MemoryAvailability.UNAVAILABLE
        or bool(str(health.last_error or "").strip())
    )

    if recovery_needed:
        status = MemoryResilienceStatus.RECOVERY_NEEDED
        reason = "memory_recovery_needed"
    elif health.is_degraded:
        status = MemoryResilienceStatus.DEGRADED
        reason = "memory_health_degraded"
    elif shared_bridge_lagging:
        status = MemoryResilienceStatus.SHARED_BRIDGE_LAGGING
        reason = "shared_bridge_lagging"
    elif fallback_active:
        status = MemoryResilienceStatus.FALLBACK_ACTIVE
        reason = "memory_fallback_active"
    else:
        status = MemoryResilienceStatus.PRIMARY_OK
        reason = "ok"

    return MemoryResilienceAssessment(
        status=status,
        degraded=status != MemoryResilienceStatus.PRIMARY_OK,
        fallback_active=fallback_active,
        shared_bridge_lagging=shared_bridge_lagging,
        recovery_needed=recovery_needed,
        reason=reason,
        total_records=safe_total,
        shared_seen_records=safe_seen,
        shared_accepted_records=safe_accepted,
        shared_rejected_records=safe_rejected,
        shared_skipped_records=safe_skipped,
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


DEFAULT_MEMORY_RESILIENCE_POLICY = MemoryResiliencePolicy()
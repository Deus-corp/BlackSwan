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


DEFAULT_MEMORY_RESILIENCE_POLICY = MemoryResiliencePolicy()
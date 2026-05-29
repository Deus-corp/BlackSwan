"""Cross-swarm directive protocol.

Directives are structured, lifecycle-aware instructions exchanged between
Overseer, meta-agents, service swarms, and worker nodes.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class DirectiveStatus(str, Enum):
    """Lifecycle status for a directive."""

    ISSUED = "issued"
    ACKNOWLEDGED = "acknowledged"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"


class DirectiveSeverity(str, Enum):
    """Directive severity."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DirectiveTargetType(str, Enum):
    """Directive target type."""

    GLOBAL = "global"
    SWARM = "swarm"
    NODE = "node"
    CAPABILITY = "capability"


@dataclass(frozen=True, slots=True)
class Directive:
    """Structured cross-swarm instruction."""

    directive_id: str
    action: str
    source: str
    target_type: str
    target: str
    payload: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    severity: str = DirectiveSeverity.INFO.value
    status: str = DirectiveStatus.ISSUED.value
    ttl_ms: int | None = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        object.__setattr__(self, "directive_id", _clean_required(self.directive_id, "directive_id"))
        object.__setattr__(self, "action", _clean_required(self.action, "action").upper())
        object.__setattr__(self, "source", _clean_required(self.source, "source"))
        object.__setattr__(self, "target_type", normalize_target_type(self.target_type))
        object.__setattr__(self, "target", _clean_required(self.target, "target"))
        object.__setattr__(self, "payload", _safe_dict(self.payload))
        object.__setattr__(self, "reason", str(self.reason or "").strip())
        object.__setattr__(self, "severity", normalize_severity(self.severity))
        object.__setattr__(self, "status", normalize_status(self.status))
        object.__setattr__(self, "ttl_ms", _safe_ttl(self.ttl_ms))
        object.__setattr__(self, "created_at", _safe_float(self.created_at, time.time()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize directive to a plain dictionary."""
        return {
            "type": "swarm_directive",
            "directive_id": self.directive_id,
            "action": self.action,
            "source": self.source,
            "target_type": self.target_type,
            "target": self.target,
            "payload": dict(self.payload),
            "reason": self.reason,
            "severity": self.severity,
            "status": self.status,
            "ttl_ms": self.ttl_ms,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class DirectiveResult:
    """Result/receipt for a directive lifecycle step."""

    result_id: str
    directive_id: str
    status: str
    source: str
    swarm: str
    node_id: str | None = None
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _clean_required(self.result_id, "result_id"))
        object.__setattr__(self, "directive_id", _clean_required(self.directive_id, "directive_id"))
        object.__setattr__(self, "status", normalize_status(self.status))
        object.__setattr__(self, "source", _clean_required(self.source, "source"))
        object.__setattr__(self, "swarm", _clean_required(self.swarm, "swarm"))

        if self.node_id is not None:
            node_id = str(self.node_id).strip()
            object.__setattr__(self, "node_id", node_id or None)

        object.__setattr__(self, "message", str(self.message or "").strip())
        object.__setattr__(self, "payload", _safe_dict(self.payload))
        object.__setattr__(self, "created_at", _safe_float(self.created_at, time.time()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize directive result to a plain dictionary."""
        return {
            "type": "swarm_directive_result",
            "result_id": self.result_id,
            "directive_id": self.directive_id,
            "status": self.status,
            "source": self.source,
            "swarm": self.swarm,
            "node_id": self.node_id,
            "message": self.message,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


def build_directive(
    *,
    action: str,
    source: str,
    target_type: str,
    target: str,
    payload: Mapping[str, Any] | None = None,
    reason: str = "",
    severity: str = DirectiveSeverity.INFO.value,
    status: str = DirectiveStatus.ISSUED.value,
    ttl_ms: int | None = None,
    directive_id: str | None = None,
    created_at: float | None = None,
) -> Directive:
    """Build a normalized directive."""
    return Directive(
        directive_id=str(directive_id or uuid.uuid4().hex),
        action=action,
        source=source,
        target_type=target_type,
        target=target,
        payload=dict(payload or {}),
        reason=reason,
        severity=severity,
        status=status,
        ttl_ms=ttl_ms,
        created_at=float(created_at if created_at is not None else time.time()),
    )


def normalize_directive(data: Mapping[str, Any] | Directive) -> Directive:
    """Normalize a raw mapping or Directive into a Directive."""
    if isinstance(data, Directive):
        return data

    if not isinstance(data, Mapping):
        raise TypeError(f"Directive data must be a mapping, got {type(data).__name__}")

    return build_directive(
        directive_id=str(data.get("directive_id") or data.get("id") or uuid.uuid4().hex),
        action=str(data.get("action") or data.get("command") or data.get("command_type") or ""),
        source=str(data.get("source") or data.get("source_swarm") or "unknown"),
        target_type=str(data.get("target_type") or _infer_target_type(data)),
        target=str(data.get("target") or data.get("target_swarm") or data.get("target_node") or "*"),
        payload=_safe_dict(data.get("payload") or {}),
        reason=str(data.get("reason") or ""),
        severity=str(data.get("severity") or DirectiveSeverity.INFO.value),
        status=str(data.get("status") or DirectiveStatus.ISSUED.value),
        ttl_ms=data.get("ttl_ms"),
        created_at=_safe_float(data.get("created_at") or data.get("timestamp"), time.time()),
    )


def build_directive_result(
    *,
    directive_id: str,
    status: str,
    source: str,
    swarm: str,
    node_id: str | None = None,
    message: str = "",
    payload: Mapping[str, Any] | None = None,
    result_id: str | None = None,
    created_at: float | None = None,
) -> DirectiveResult:
    """Build a normalized directive result."""
    return DirectiveResult(
        result_id=str(result_id or uuid.uuid4().hex),
        directive_id=directive_id,
        status=status,
        source=source,
        swarm=swarm,
        node_id=node_id,
        message=message,
        payload=dict(payload or {}),
        created_at=float(created_at if created_at is not None else time.time()),
    )


def normalize_directive_result(data: Mapping[str, Any] | DirectiveResult) -> DirectiveResult:
    """Normalize a raw mapping or DirectiveResult into a DirectiveResult."""
    if isinstance(data, DirectiveResult):
        return data

    if not isinstance(data, Mapping):
        raise TypeError(f"DirectiveResult data must be a mapping, got {type(data).__name__}")

    return build_directive_result(
        result_id=str(data.get("result_id") or data.get("id") or uuid.uuid4().hex),
        directive_id=str(data.get("directive_id") or ""),
        status=str(data.get("status") or DirectiveStatus.ACKNOWLEDGED.value),
        source=str(data.get("source") or "unknown"),
        swarm=str(data.get("swarm") or data.get("source_swarm") or "unknown"),
        node_id=_optional_str(data.get("node_id") or data.get("source_node")),
        message=str(data.get("message") or ""),
        payload=_safe_dict(data.get("payload") or {}),
        created_at=_safe_float(data.get("created_at") or data.get("timestamp"), time.time()),
    )


def directive_is_expired(directive: Mapping[str, Any] | Directive, *, now: float | None = None) -> bool:
    """Return True if directive TTL has expired."""
    normalized = normalize_directive(directive)
    if normalized.ttl_ms is None:
        return False

    current = float(now if now is not None else time.time())
    age_ms = max(0.0, current - normalized.created_at) * 1000.0
    return age_ms > normalized.ttl_ms


def directive_targets_swarm(
    directive: Mapping[str, Any] | Directive,
    *,
    swarm: str,
) -> bool:
    """Return True if directive targets a swarm."""
    normalized = normalize_directive(directive)
    target = normalized.target.lower()
    swarm_name = str(swarm or "").strip().lower()

    if normalized.target_type == DirectiveTargetType.GLOBAL.value:
        return True

    if normalized.target_type == DirectiveTargetType.SWARM.value:
        return target in {"*", "all", swarm_name}

    return False


def directive_targets_node(
    directive: Mapping[str, Any] | Directive,
    *,
    swarm: str,
    node_id: str,
    capabilities: Iterable[str] | None = None,
) -> bool:
    """Return True if directive targets this node, swarm, global scope, or capability."""
    normalized = normalize_directive(directive)
    target = normalized.target.lower()
    swarm_name = str(swarm or "").strip().lower()
    clean_node_id = str(node_id or "").strip().lower()

    if normalized.target_type == DirectiveTargetType.GLOBAL.value:
        return True

    if normalized.target_type == DirectiveTargetType.SWARM.value:
        return target in {"*", "all", swarm_name}

    if normalized.target_type == DirectiveTargetType.NODE.value:
        return target in {"*", "all", clean_node_id}

    if normalized.target_type == DirectiveTargetType.CAPABILITY.value:
        caps = {str(item).strip().lower() for item in capabilities or [] if str(item).strip()}
        return target in caps

    return False


def directive_to_record(directive: Mapping[str, Any] | Directive) -> dict[str, Any]:
    """Convert directive into a CRDT/event-friendly record."""
    normalized = normalize_directive(directive)
    return normalized.to_dict()


def directive_result_to_record(result: Mapping[str, Any] | DirectiveResult) -> dict[str, Any]:
    """Convert directive result into a CRDT/event-friendly record."""
    normalized = normalize_directive_result(result)
    return normalized.to_dict()


def normalize_status(value: Any) -> str:
    """Normalize directive lifecycle status."""
    raw = str(value or DirectiveStatus.ISSUED.value).strip().lower()
    allowed = {item.value for item in DirectiveStatus}
    return raw if raw in allowed else DirectiveStatus.ISSUED.value


def normalize_severity(value: Any) -> str:
    """Normalize directive severity."""
    raw = str(value or DirectiveSeverity.INFO.value).strip().lower()
    allowed = {item.value for item in DirectiveSeverity}
    return raw if raw in allowed else DirectiveSeverity.INFO.value


def normalize_target_type(value: Any) -> str:
    """Normalize directive target type."""
    raw = str(value or DirectiveTargetType.GLOBAL.value).strip().lower()
    allowed = {item.value for item in DirectiveTargetType}
    return raw if raw in allowed else DirectiveTargetType.GLOBAL.value


def _infer_target_type(data: Mapping[str, Any]) -> str:
    if data.get("target_node") or data.get("node_id"):
        return DirectiveTargetType.NODE.value
    if data.get("target_swarm") or data.get("swarm"):
        return DirectiveTargetType.SWARM.value
    return DirectiveTargetType.GLOBAL.value


def _clean_required(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must be a non-empty string")
    return text


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_ttl(value: Any) -> int | None:
    if value is None:
        return None
    try:
        ttl = int(value)
    except (TypeError, ValueError):
        return None
    return ttl if ttl > 0 else None


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "Directive",
    "DirectiveResult",
    "DirectiveSeverity",
    "DirectiveStatus",
    "DirectiveTargetType",
    "build_directive",
    "build_directive_result",
    "directive_is_expired",
    "directive_result_to_record",
    "directive_targets_node",
    "directive_targets_swarm",
    "directive_to_record",
    "normalize_directive",
    "normalize_directive_result",
    "normalize_severity",
    "normalize_status",
    "normalize_target_type",
]
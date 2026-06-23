"""LLM-friendly swarm brief protocol.

A SwarmBrief is a compact, structured summary of a swarm, node, or global
runtime state. It is designed to reduce noisy log-scanning and provide agents
with actionable context, evidence links, risks, and recommended next actions.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from ._utils import (
    clean_required as _clean_required,
    optional_str as _optional_str,
    safe_dict as _safe_dict,
    safe_float as _safe_float,
    safe_str_list as _safe_str_list,
    safe_items as _safe_items,
)


class BriefStatus(str, Enum):
    """High-level operational status for a brief subject."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class BriefSeverity(str, Enum):
    """Severity for risks, opportunities, and recommended actions."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class BriefScope(str, Enum):
    """Scope of a brief."""

    GLOBAL = "global"
    SWARM = "swarm"
    NODE = "node"


@dataclass(frozen=True, slots=True)
class SwarmBrief:
    """Compact operational context for LLM/agent synchronization."""

    brief_id: str
    scope: str
    status: str
    summary: str
    swarm: str | None = None
    node_id: str | None = None
    key_metrics: dict[str, Any] = field(default_factory=dict)
    risks: list[dict[str, Any]] = field(default_factory=list)
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        object.__setattr__(self, "brief_id", _clean_required(self.brief_id, "brief_id"))
        object.__setattr__(self, "scope", normalize_scope(self.scope))
        object.__setattr__(self, "status", normalize_status(self.status))
        object.__setattr__(self, "summary", str(self.summary or "").strip())

        if self.swarm is not None:
            swarm = str(self.swarm).strip()
            object.__setattr__(self, "swarm", swarm or None)

        if self.node_id is not None:
            node_id = str(self.node_id).strip()
            object.__setattr__(self, "node_id", node_id or None)

        object.__setattr__(self, "key_metrics", _safe_dict(self.key_metrics))
        object.__setattr__(self, "risks", _safe_items(self.risks))
        object.__setattr__(self, "opportunities", _safe_items(self.opportunities))
        object.__setattr__(self, "recommended_actions", _safe_items(self.recommended_actions))
        object.__setattr__(self, "evidence_ids", _safe_str_list(self.evidence_ids))
        object.__setattr__(self, "created_at", _safe_float(self.created_at, time.time()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize brief to a plain dictionary."""
        return {
            "brief_id": self.brief_id,
            "type": "swarm_brief",
            "scope": self.scope,
            "swarm": self.swarm,
            "node_id": self.node_id,
            "status": self.status,
            "summary": self.summary,
            "key_metrics": dict(self.key_metrics),
            "risks": [dict(item) for item in self.risks],
            "opportunities": [dict(item) for item in self.opportunities],
            "recommended_actions": [dict(item) for item in self.recommended_actions],
            "evidence_ids": list(self.evidence_ids),
            "created_at": self.created_at,
        }


def build_swarm_brief(
    *,
    scope: str,
    status: str = BriefStatus.UNKNOWN.value,
    summary: str = "",
    swarm: str | None = None,
    node_id: str | None = None,
    key_metrics: Mapping[str, Any] | None = None,
    risks: Iterable[Mapping[str, Any]] | None = None,
    opportunities: Iterable[Mapping[str, Any]] | None = None,
    recommended_actions: Iterable[Mapping[str, Any]] | None = None,
    evidence_ids: Iterable[Any] | None = None,
    brief_id: str | None = None,
    created_at: float | None = None,
) -> SwarmBrief:
    """Build a normalized SwarmBrief."""
    return SwarmBrief(
        brief_id=str(brief_id or uuid.uuid4().hex),
        scope=scope,
        status=status,
        summary=summary,
        swarm=swarm,
        node_id=node_id,
        key_metrics=dict(key_metrics or {}),
        risks=[dict(item) for item in risks or [] if isinstance(item, Mapping)],
        opportunities=[dict(item) for item in opportunities or [] if isinstance(item, Mapping)],
        recommended_actions=[dict(item) for item in recommended_actions or [] if isinstance(item, Mapping)],
        evidence_ids=list(evidence_ids or []),
        created_at=float(created_at if created_at is not None else time.time()),
    )


def normalize_swarm_brief(data: Mapping[str, Any] | SwarmBrief) -> SwarmBrief:
    """Normalize a raw mapping or SwarmBrief into a SwarmBrief."""
    if isinstance(data, SwarmBrief):
        return data

    if not isinstance(data, Mapping):
        raise TypeError(f"SwarmBrief data must be a mapping, got {type(data).__name__}")

    return build_swarm_brief(
        brief_id=str(data.get("brief_id") or data.get("id") or uuid.uuid4().hex),
        scope=str(data.get("scope") or BriefScope.GLOBAL.value),
        status=str(data.get("status") or BriefStatus.UNKNOWN.value),
        summary=str(data.get("summary") or ""),
        swarm=_optional_str(data.get("swarm") or data.get("source_swarm")),
        node_id=_optional_str(data.get("node_id") or data.get("source_node")),
        key_metrics=_safe_dict(data.get("key_metrics") or data.get("metrics") or {}),
        risks=_safe_items(data.get("risks") or []),
        opportunities=_safe_items(data.get("opportunities") or []),
        recommended_actions=_safe_items(data.get("recommended_actions") or data.get("actions") or []),
        evidence_ids=_safe_str_list(data.get("evidence_ids") or []),
        created_at=_safe_float(data.get("created_at") or data.get("timestamp"), time.time()),
    )


def brief_to_record(brief: SwarmBrief | Mapping[str, Any], *, source: str = "overseer") -> dict[str, Any]:
    """Convert a brief into a CRDT/event-friendly record."""
    normalized = normalize_swarm_brief(brief)
    row = normalized.to_dict()
    return {
        "type": "swarm_brief",
        "brief_id": normalized.brief_id,
        "source": str(source or "overseer"),
        "scope": normalized.scope,
        "swarm": normalized.swarm,
        "node_id": normalized.node_id,
        "status": normalized.status,
        "payload": row,
        "timestamp": normalized.created_at,
    }


def normalize_status(value: Any) -> str:
    """Normalize brief status."""
    raw = str(value or BriefStatus.UNKNOWN.value).strip().lower()
    allowed = {item.value for item in BriefStatus}
    return raw if raw in allowed else BriefStatus.UNKNOWN.value


def normalize_scope(value: Any) -> str:
    """Normalize brief scope."""
    raw = str(value or BriefScope.GLOBAL.value).strip().lower()
    allowed = {item.value for item in BriefScope}
    return raw if raw in allowed else BriefScope.GLOBAL.value


def build_brief_item(
    *,
    title: str,
    severity: str = BriefSeverity.INFO.value,
    detail: str = "",
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized risk/opportunity/action item."""
    return {
        "title": str(title or "").strip(),
        "severity": normalize_severity(severity),
        "detail": str(detail or "").strip(),
        "payload": dict(payload or {}),
    }


def normalize_severity(value: Any) -> str:
    """Normalize item severity."""
    raw = str(value or BriefSeverity.INFO.value).strip().lower()
    allowed = {item.value for item in BriefSeverity}
    return raw if raw in allowed else BriefSeverity.INFO.value


__all__ = [
    "BriefScope",
    "BriefSeverity",
    "BriefStatus",
    "SwarmBrief",
    "brief_to_record",
    "build_brief_item",
    "build_swarm_brief",
    "normalize_scope",
    "normalize_severity",
    "normalize_status",
    "normalize_swarm_brief",
]
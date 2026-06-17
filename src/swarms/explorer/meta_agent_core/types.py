from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

EventType = Literal[
    "finding_received",
    "classification_started",
    "finding_classified",
    "targets_suggested",
    "memory_handoff_published",
]


class ExplorerEvent(TypedDict, total=False):
    type: Literal["explorer_event"]
    event_type: EventType
    gid: str
    source_gid: str
    parent_gid: Optional[str]
    timestamp: float
    provenance: Dict[str, Any]
    data: Dict[str, Any]


class ExplorerFinding(TypedDict, total=False):
    type: Literal["explorer_finding"]
    source_gid: str
    url: Optional[str]
    content_preview: Optional[str]
    classification: Literal["USEFUL", "HARMFUL", "NEUTRAL", "unclassified"]
    confidence: float
    reason: str
    timestamp: float
    gid: str
    domain: Optional[str]
    content_hash: Optional[str]
    fetch_status: str
    fetch_error: Optional[str]
    event_type: Optional[str]
    provenance: Dict[str, Any]


class ClassificationItem(TypedDict):
    source_gid: str
    url: Optional[str]
    classification: Literal["USEFUL", "HARMFUL", "NEUTRAL"]
    confidence: float
    reason: str


class ExplorerTargetsData(TypedDict):
    urls: List[str]


class ExplorerTargets(TypedDict):
    type: Literal["explorer_targets"]
    event_type: Literal["targets_suggested"]
    data: ExplorerTargetsData
    source_gids: List[str]
    timestamp: float
    gid: str
    provenance: Dict[str, Any]
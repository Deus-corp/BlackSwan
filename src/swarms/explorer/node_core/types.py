from __future__ import annotations

from typing import Any, Dict, Literal, Optional, TypedDict

EventType = Literal[
    "target_received",
    "fetch_started",
    "fetch_failed",
    "content_extracted",
    "finding_published",
    "targets_discovered",
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
    event_type: Literal["finding_published"]
    gid: str
    source_gid: str
    url: Optional[str]
    domain: Optional[str]
    content_preview: Optional[str]
    content_hash: Optional[str]
    fetch_status: str
    fetch_error: Optional[str]
    classification: Literal["USEFUL", "HARMFUL", "NEUTRAL", "unclassified"]
    confidence: float
    reason: str
    timestamp: float
    provenance: Dict[str, Any]

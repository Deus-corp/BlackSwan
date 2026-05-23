#!/usr/bin/env python3
"""Explorer node core package.

Specialized building blocks for ExplorerNode:
- SQLite node memory
- local crawl/fetch policy
- type contracts
- URL/content utilities
"""

from __future__ import annotations

from .memory import NodeMemory
from .policy import NodePolicy
from .types import EventType, ExplorerEvent, ExplorerFinding
from .utils import (
    extract_domain,
    fingerprint_text,
    is_valid_http_url,
    make_content_preview,
    normalize_url,
)

__all__ = [
    "EventType",
    "ExplorerEvent",
    "ExplorerFinding",
    "NodeMemory",
    "NodePolicy",
    "extract_domain",
    "fingerprint_text",
    "is_valid_http_url",
    "make_content_preview",
    "normalize_url",
]
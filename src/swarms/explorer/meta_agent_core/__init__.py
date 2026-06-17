#!/usr/bin/env python3
"""Explorer meta-agent core package.

Specialized building blocks for ExplorerMetaAgent:
- SQLite memory
- parsing helpers
- prompt builders
- target ranking
- type contracts
- utility helpers
"""

from __future__ import annotations

from .memory import MetaAgentMemory
from .parsing import extract_json_object, normalize_classification_item
from .prompts import build_classification_prompt, build_target_prompt
from .ranking import rank_and_deduplicate_targets, score_targets
from .types import (
    ClassificationItem,
    EventType,
    ExplorerEvent,
    ExplorerFinding,
    ExplorerTargets,
)
from .utils import (
    extract_domain,
    is_probably_valid_url,
    normalize_url,
    prompt_hash,
)
from .source_adapters import (
    DEFAULT_SOURCE_ADAPTERS,
    build_source_adapter_targets,
)
from .source_scoring import score_source_target

__all__ = [
    "ClassificationItem",
    "EventType",
    "ExplorerEvent",
    "ExplorerFinding",
    "ExplorerTargets",
    "MetaAgentMemory",
    "build_classification_prompt",
    "build_target_prompt",
    "extract_domain",
    "extract_json_object",
    "is_probably_valid_url",
    "normalize_classification_item",
    "normalize_url",
    "prompt_hash",
    "rank_and_deduplicate_targets",
    "score_targets",
    "DEFAULT_SOURCE_ADAPTERS",
    "build_source_adapter_targets",
    "score_source_target",
]
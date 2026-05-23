#!/usr/bin/env python3
"""Security swarm package.

Public entrypoints:
- SecurityNode: local defensive execution node
- SecurityMetaAgent: swarm-level security coordinator
"""

from __future__ import annotations

from .meta_agent import SecurityMetaAgent
from .node import SecurityNode

__all__ = [
    "SecurityMetaAgent",
    "SecurityNode",
]
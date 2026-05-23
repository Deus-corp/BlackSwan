#!/usr/bin/env python3
"""Overseer swarm package.

The Overseer is the global orchestration layer above all swarm ecosystems.

Public entrypoint:
- OverseerNode
"""

from __future__ import annotations

from .node import OverseerNode

__all__ = [
    "OverseerNode",
]
#!/usr/bin/env python3
"""Improver swarm package.

The Improver is a maintenance/code-improvement swarm.

Public entrypoint:
- ImproverAgent
"""

from __future__ import annotations

from .improver_agent import ImproverAgent

__all__ = [
    "ImproverAgent",
]
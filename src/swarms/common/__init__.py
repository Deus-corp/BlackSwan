#!/usr/bin/env python3
"""Common swarm runtime package.

This package contains shared runtime primitives used by all swarm ecosystems:

- BaseSwarmNode
- BaseSwarmMetaAgent
- BaseSwarmOverseer
- shared runtime configs
- generic decision containers

Specialized swarms should import from this package instead of depending on
another swarm's implementation details.
"""

from __future__ import annotations

from .base import (
    BaseMetaAgentConfig,
    BaseNodeConfig,
    BaseOverseerConfig,
    BaseSwarmMetaAgent,
    BaseSwarmNode,
    BaseSwarmOverseer,
    GlobalDecision,
    MetaAgentHealth,
    MetaDecision,
    NodeHealth,
    OverseerHealth,
)

__all__ = [
    "BaseMetaAgentConfig",
    "BaseNodeConfig",
    "BaseOverseerConfig",
    "BaseSwarmMetaAgent",
    "BaseSwarmNode",
    "BaseSwarmOverseer",
    "GlobalDecision",
    "MetaAgentHealth",
    "MetaDecision",
    "NodeHealth",
    "OverseerHealth",
]
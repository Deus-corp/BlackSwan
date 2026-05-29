"""Trade meta-agent core package."""

from __future__ import annotations

from src.swarms.trade.meta_agent_core.service import (
    CRDTAdapterProtocol,
    LLMClientProtocol,
    MetaAgentNode,
    main,
)

__all__ = [
    "CRDTAdapterProtocol",
    "LLMClientProtocol",
    "MetaAgentNode",
    "main",
]
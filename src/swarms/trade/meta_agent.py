"""Trade meta-agent entrypoint.

The implementation lives in src.swarms.trade.meta_agent_core.service.
"""

from __future__ import annotations

import asyncio

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


if __name__ == "__main__":
    asyncio.run(main())
"""Trade swarm node entrypoint.

The implementation lives in src.swarms.trade.node_core.service.
"""

from __future__ import annotations

import asyncio

from src.swarms.trade.node_core.service import SwarmNode, main

__all__ = [
    "SwarmNode",
    "main",
]


if __name__ == "__main__":
    asyncio.run(main())
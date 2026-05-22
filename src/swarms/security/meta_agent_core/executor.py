#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any, Dict

from src.swarms.security.node_core import new_gid, now_ts


class SecurityExecutor:
    def __init__(self, crdt, node_id: str) -> None:
        self.crdt = crdt
        self.node_id = node_id

    async def dispatch(self, action: str, rationale: str) -> Dict[str, Any]:
        command = {
            "type": "sec_command",
            "event_type": "command_issued",
            "gid": new_gid("sec_cmd"),
            "source_gid": self.node_id,
            "parent_gid": None,
            "timestamp": time.time(),
            "expires_at": now_ts() + 600,
            "provenance": {
                "agent": self.node_id,
            },
            "data": {
                "action": action,
                "rationale": rationale,
            },
        }

        await self.crdt.add_genome(command)

        return command
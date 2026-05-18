#!/usr/bin/env python3
"""
Security MetaAgent – анализирует угрозы и управляет роем безопасности.
"""
import asyncio
import logging
import os
import sys
import time
import uuid
import json
from typing import Dict, Any, List

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("SecurityMetaAgent")

class SecurityMetaAgent:
    """
    SecurityMetaAgent analyzes threats and manages the security swarm.
    It periodically reflects on the overall security state via CRDT and issues commands.
    """
    def __init__(self, node_id: str = None) -> None:
        """
        Initializes the SecurityMetaAgent with a unique ID, LLM client, and CRDT adapter.
        """
        self.node_id: str = node_id or f"sec-meta-{uuid.uuid4().hex[:8]}"
        self.llm: LLMClient = LLMClient(n_ctx=4096)
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.step: int = 0

    async def run(self) -> None:
        """
        Starts the main loop for the SecurityMetaAgent, periodically reflecting on security state.
        """
        logger.info(f"🔐 SecurityMetaAgent {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 100 == 0:
                await self.reflect()
            await asyncio.sleep(1.0)

    async def reflect(self) -> None:
        """
        Reflects on the current security state by checking heartbeats from security nodes
        and uses an LLM to decide on actions, such as unblocking all IPs.
        """
        try:
            all_state: Dict[str, Any] = self.crdt.state
            heartbeats: List[Dict[str, Any]] = [
                v for k, v in all_state.items()
                if isinstance(v, dict) and v.get("type") == "security_heartbeat"
            ]
            blocked: int = sum(h.get("blocked_ips", 0) for h in heartbeats)

            prompt: str = f"""User: You are a cybersecurity AI. Swarm status: {len(heartbeats)} nodes reporting, {blocked} IPs blocked.
Do you recommend unblocking all IPs? Answer ONLY "YES" or "NO".
Assistant: """
            response: str = self.llm.generate(prompt, max_tokens=10, temperature=0.1)
            if response and "YES" in response.upper():
                cmd: Dict[str, Any] = {
                    "type": "sec_command",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": time.time(),
                    "expires_at": time.time() + 600,
                    "gid": f"sec_cmd_{int(time.time())}",
                }
                await self.crdt.add_genome(cmd)
                logger.info("🔓 SecurityMetaAgent: recommended unblocking all IPs")
        except Exception as e:
            logger.error(f"SecurityMetaAgent reflection failed: {e}", exc_info=True)

if __name__ == "__main__":
    node = SecurityMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("SecurityMetaAgent stopped.")
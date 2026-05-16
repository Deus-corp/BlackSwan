#!/usr/bin/env python3
"""
Overseer Node – координирует всех MetaAgent'ов через LLM.
"""
import asyncio, logging, os, sys, time, uuid, json
from typing import Dict, Any, List

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("Overseer")

class OverseerNode:
    def __init__(self):
        self.node_id = f"overseer-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient(n_ctx=4096)
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.step = 0

    async def run(self):
        logger.info(f"🧭 Overseer {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 300 == 0:
                await self.coordinate()
            await asyncio.sleep(1.0)

    async def coordinate(self):
        try:
            all_state = self.crdt.state
            # Агрегируем Trade heartbeats
            trade_hbs = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "heartbeat"]
            trade_nodes = len(set(h.get("node_id") for h in trade_hbs))
            trade_capital = sum(h.get("capital", 0) for h in trade_hbs)
            trade_dq = sum(h.get("dq", 0) for h in trade_hbs) / max(len(trade_hbs), 1)
            # Агрегируем Security heartbeats
            sec_hbs = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "security_heartbeat"]
            sec_nodes = len(set(h.get("node_id") for h in sec_hbs))
            blocked_ips = sum(h.get("blocked_ips", 0) for h in sec_hbs)

            prompt = f"""User: You coordinate a Trade swarm ({trade_nodes} nodes, capital {trade_capital:.0f}, DQ {trade_dq:.3f}) and a Security swarm ({sec_nodes} nodes, {blocked_ips} IPs blocked).
Should you reduce trade risk? Answer "YES" or "NO". Should you unblock all IPs? Answer "YES" or "NO".
Assistant: """
            response = self.llm.generate(prompt, max_tokens=30, temperature=0.1)
            if response:
                if "YES" in response and "reduce trade risk" in prompt:
                    cmd = {
                        "type": "meta_command_json",
                        "data": {"action": "ADJUST_SWARM", "params": {"risk_scale": 0.7}, "reason": "Overseer safety override"},
                        "timestamp": time.time(),
                        "expires_at": time.time() + 300,
                        "gid": f"overseer_{int(time.time())}",
                    }
                    await self.crdt.add_genome(cmd)
                    logger.info("🧭 Overseer: reducing trade risk")
                if "YES" in response and "unblock all IPs" in prompt:
                    cmd = {
                        "type": "sec_command",
                        "data": {"action": "UNBLOCK_ALL"},
                        "timestamp": time.time(),
                        "expires_at": time.time() + 600,
                        "gid": f"overseer_sec_{int(time.time())}",
                    }
                    await self.crdt.add_genome(cmd)
                    logger.info("🔓 Overseer: requesting unblock all IPs")
        except Exception as e:
            logger.error(f"Overseer coordination failed: {e}")

if __name__ == "__main__":
    node = OverseerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("Overseer stopped.")
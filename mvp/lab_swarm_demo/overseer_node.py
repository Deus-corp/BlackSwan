#!/usr/bin/env python3
"""
Overseer Node – стратегический координатор для Trade и Security роев.
Анализирует heartbeats обоих роев и выдаёт JSON-команды через LLM.
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
            trade_fitness = sum(h.get("fitness", 0) for h in trade_hbs) / max(len(trade_hbs), 1)

            # Агрегируем Security heartbeats
            sec_hbs = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "security_heartbeat"]
            sec_nodes = len(set(h.get("node_id") for h in sec_hbs))
            blocked_ips = sum(h.get("blocked_ips", 0) for h in sec_hbs)
            resources = self._get_resource_context()

            prompt = f"""User: You are BlackSwan Overseer, a strategic coordinator for two swarms:
- Trade swarm: {trade_nodes} nodes, total capital {trade_capital:.0f}, DQ {trade_dq:.3f}, fitness {trade_fitness:.3f}
- Security swarm: {sec_nodes} nodes, {blocked_ips} IPs blocked
- System resources: {resources}

Decide:
1. Should you reduce trade risk? (if DQ > 0.25 or capital < 2000, answer YES)
2. Should you increase exploration? (if fitness is high and DQ is low, answer YES)
3. Should you unblock all IPs? (if blocked IPs > 50, answer YES)
4. Should you spawn more nodes? (if RAM > 500MB, answer YES)

Output ONLY a JSON with three boolean fields: reduce_risk, increase_exploration, unblock_ips.
Example: {{"reduce_risk":false,"increase_exploration":true,"unblock_ips":false}}
Assistant: {{"""
            response = self.llm.generate(prompt, max_tokens=60, temperature=0.1)
            if response:
                # Парсим JSON
                start = response.find('{')
                end = response.rfind('}')
                if start != -1 and end != -1:
                    candidate = response[start:end+1]
                    try:
                        decisions = json.loads(candidate)
                    except:
                        try:
                            decisions = json.loads(candidate + "}")
                        except:
                            return

                    # Применяем решения
                    if decisions.get("reduce_risk"):
                        cmd = {
                            "type": "meta_command_json",
                            "data": {
                                "action": "ADJUST_SWARM",
                                "params": {
                                    "exploration_multiplier": 1.0,
                                    "risk_scale": 0.7,
                                    "survival_bias_adj": 0.05,
                                    "stop_loss_adj": 0.8,
                                    "confidence": 0.9
                                },
                                "reason": "Overseer safety override"
                            },
                            "timestamp": time.time(),
                            "expires_at": time.time() + 300,
                            "gid": f"overseer_{int(time.time())}",
                        }
                        await self.crdt.add_genome(cmd)
                        logger.info("🧭 Overseer: reducing trade risk")

                    if decisions.get("increase_exploration"):
                        cmd = {
                            "type": "meta_command_json",
                            "data": {
                                "action": "ADJUST_SWARM",
                                "params": {
                                    "exploration_multiplier": 1.5,
                                    "risk_scale": 1.0,
                                    "survival_bias_adj": 0.0,
                                    "stop_loss_adj": 1.0,
                                    "confidence": 0.8
                                },
                                "reason": "Overseer: increase exploration"
                            },
                            "timestamp": time.time(),
                            "expires_at": time.time() + 300,
                            "gid": f"overseer_{int(time.time())}",
                        }
                        await self.crdt.add_genome(cmd)
                        logger.info("🧭 Overseer: increasing exploration")

                    if decisions.get("unblock_ips"):
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

    def _get_resource_context(self) -> str:
        """Собирает системные метрики для анализа ресурсов."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return (
                f"CPU: {cpu:.1f}%, RAM: {mem.percent:.1f}% ({mem.available//1024//1024}MB free), "
                f"Disk: {disk.percent:.1f}% ({disk.free//1024//1024}MB free)"
            )
        except ImportError:
            return "Resource data unavailable (psutil not installed)"
        except Exception as e:
            logger.warning(f"Resource check failed: {e}")
            return f"Resource check failed: {e}"

if __name__ == "__main__":
    node = OverseerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("Overseer stopped.")
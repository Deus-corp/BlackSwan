#!/usr/bin/env python3
"""
Overseer Node – стратегический координатор для Trade, Security и Explorer роев.
Анализирует heartbeats всех роев и выдаёт JSON-команды через LLM.
"""
import asyncio
import logging
import os
import sys
import time
import uuid
import json
from typing import Dict, Any, List
import re

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("Overseer")

class OverseerNode:
    """
    OverseerNode acts as a strategic coordinator, analyzing heartbeats from Trade, Security,
    and Explorer swarms and issuing JSON commands via an LLM.
    """
    def __init__(self, node_id: str = None) -> None:
        """
        Initializes the OverseerNode with a unique ID, LLM client, and CRDT adapter.
        """
        self.node_id: str = node_id or f"overseer-{uuid.uuid4().hex[:8]}"
        self.llm: LLMClient = LLMClient(n_ctx=8192)
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.step: int = 0

    async def run(self) -> None:
        """
        Starts the main loop for the OverseerNode, periodically coordinating swarm activities.
        """
        logger.info(f"🧭 Overseer {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 150 == 0:
                await self.coordinate()
            await asyncio.sleep(1.0)

    async def coordinate(self) -> None:
        """
        Coordinates the swarms by analyzing their state and issuing commands based on LLM decisions.
        Aggregates heartbeats and other data from CRDT, forms a prompt for the LLM,
        parses the LLM's JSON response, and applies the decisions by adding new genomes to CRDT.
        """
        try:
            all_state: Dict[str, Any] = self.crdt.state
            now: float = time.time()

            # Initialize decisions dictionary to prevent potential KeyError before LLM response
            decisions: Dict[str, Any] = {}

            # Агрегируем Trade heartbeats
            # Assuming 'trade_heartbeat' type for trade nodes for distinct aggregation.
            # If trade nodes send a generic 'heartbeat', this filter should be adjusted accordingly.
            trade_hbs: List[Dict[str, Any]] = [
                v for k, v in all_state.items()
                if isinstance(v, dict) and v.get("type") == "trade_heartbeat"
                and now - v.get("timestamp", 0) < 600
            ]
            trade_nodes: int = len(set(h.get("node_id") for h in trade_hbs))
            trade_capital: float = sum(h.get("capital", 0.0) for h in trade_hbs)
            trade_dq: float = sum(h.get("dq", 0.0) for h in trade_hbs) / max(len(trade_hbs), 1)
            trade_fitness: float = sum(h.get("fitness", 0.0) for h in trade_hbs) / max(len(trade_hbs), 1)

            # Проверяем истёкшие heartbeats (>180 секунд)
            stale_nodes: List[str] = [
                h.get("node_id") for h in trade_hbs
                if now - h.get("timestamp", 0) > 180
            ]
            if stale_nodes:
                for node_id_stale in set(stale_nodes):
                    cmd_restart: Dict[str, Any] = {
                        "type": "sec_command",
                        "data": {"action": "RESTART_NODE", "node_id": node_id_stale},
                        "timestamp": now,
                        "expires_at": now + 300,
                        "gid": f"overseer_restart_{int(now)}",
                    }
                    await self.crdt.add_genome(cmd_restart)
                    logger.info(f"🔄 Overseer: requesting restart of stale node {node_id_stale}")

            # Агрегируем Security heartbeats
            # Corrected filter type to "security_heartbeat" as used by security_node_agent.py
            sec_hbs: List[Dict[str, Any]] = [
                v for k, v in all_state.items()
                if isinstance(v, dict) and v.get("type") == "security_heartbeat"
                and now - v.get("timestamp", 0) < 600
            ]
            sec_nodes: int = len(set(h.get("node_id") for h in sec_hbs))
            blocked_ips: int = sum(h.get("blocked_ips", 0) for h in sec_hbs)

            # Проверяем уязвимости от Security
            vuln_alerts: List[Dict[str, Any]] = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "vulnerability_alert"]
            if vuln_alerts:
                logger.warning("🔴 Overseer: vulnerabilities detected, reducing trade risk")
                decisions["reduce_risk"] = True  # принудительно

            # Explorer heartbeats
            # Assuming 'explorer_heartbeat' type for explorer nodes for distinct aggregation.
            # If explorer nodes send a generic 'heartbeat', this filter should be adjusted accordingly.
            exp_hbs: List[Dict[str, Any]] = [
                v for k, v in all_state.items()
                if isinstance(v, dict) and v.get("type") == "explorer_heartbeat"
                and now - v.get("timestamp", 0) < 600
            ]
            exp_nodes: int = len(set(h.get("node_id") for h in exp_hbs))
            findings: int = len([v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "explorer_finding"])

            resources: str = self._get_resource_context()

            prompt: str = f"""User: You are BlackSwan Overseer, a strategic coordinator for three swarms:
- Trade swarm: {trade_nodes} nodes, total capital {trade_capital:.0f}, DQ {trade_dq:.3f}, fitness {trade_fitness:.3f}
- Security swarm: {sec_nodes} nodes, {blocked_ips} IPs blocked
- Explorer swarm: {exp_nodes} nodes, {findings} findings
- System resources: {resources}

Decide:
1. Should you reduce trade risk? (if DQ > 0.25 or capital < 2000, answer YES)
2. Should you increase exploration? (if fitness is high and DQ is low, answer YES)
3. Should you unblock all IPs? (if blocked IPs > 50, answer YES)
4. Should you spawn more nodes? (if RAM > 500MB, answer YES)
5. Should the Explorer continue? (if findings > 100, answer NO)

Output ONLY a JSON with these boolean fields: reduce_risk, increase_exploration, unblock_ips, spawn_nodes, continue_explorer.
Example: {{"reduce_risk":false,"increase_exploration":true,"unblock_ips":false,"spawn_nodes":false,"continue_explorer":true}}
Assistant: {{"""
            response: str = self.llm.generate(prompt, max_tokens=80, temperature=0.1)
            if response:
                # Исправляем пропущенную кавычку перед первым ключом (common LLM JSON error)
                response = re.sub(r'\{(\w+)"\s*:', r'{"\1":', response)

                # Нормализуем JSON: добавляем скобки, если их нет
                if not response.strip().startswith('{'):
                    response = '{' + response
                if not response.strip().endswith('}'):
                    response = response + '}'
                logger.info(f"Overseer normalized response: {response[:200]}")

                # Оборачиваем ключи в кавычки (common LLM JSON error)
                cleaned: str = re.sub(r'(\w+):', r'"\1":', response)

                # Ищем JSON-объект с балансировкой скобок
                start: int = cleaned.find('{')
                candidate: Optional[str] = None
                if start != -1:
                    depth: int = 0
                    end: int = start
                    for i in range(start, len(cleaned)):
                        if cleaned[i] == '{':
                            depth += 1
                        elif cleaned[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i
                                break
                    candidate = cleaned[start:end+1]
                else:
                    logger.warning("Overseer: no valid JSON object found in LLM response")
                    return

                if candidate:
                    try:
                        decisions = json.loads(candidate)
                    except json.JSONDecodeError:
                        try:
                            # Attempt to fix by adding a closing brace if missing
                            decisions = json.loads(candidate + "}")
                        except json.JSONDecodeError as e:
                            logger.warning(f"Overseer failed to parse JSON: {candidate}. Error: {e}")
                            return
                else:
                    return # No candidate JSON found

                if not decisions:
                    return

                # Применяем решения
                if decisions.get("reduce_risk"):
                    cmd_reduce_risk: Dict[str, Any] = {
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
                    await self.crdt.add_genome(cmd_reduce_risk)
                    logger.info("🧭 Overseer: reducing trade risk")

                if decisions.get("increase_exploration"):
                    cmd_increase_exploration: Dict[str, Any] = {
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
                    await self.crdt.add_genome(cmd_increase_exploration)
                    logger.info("🧭 Overseer: increasing exploration")

                if decisions.get("unblock_ips"):
                    cmd_unblock_ips: Dict[str, Any] = {
                        "type": "sec_command",
                        "data": {"action": "UNBLOCK_ALL"},
                        "timestamp": time.time(),
                        "expires_at": time.time() + 600,
                        "gid": f"overseer_sec_{int(time.time())}",
                    }
                    await self.crdt.add_genome(cmd_unblock_ips)
                    logger.info("🔓 Overseer: requesting unblock all IPs")

                if decisions.get("spawn_nodes"):
                    logger.info("🧭 Overseer: recommends spawning more nodes")
                    # TODO: автоматический скейлинг через Docker API

                if decisions.get("continue_explorer") is False:
                    cmd_pause_explorer: Dict[str, Any] = {
                        "type": "explorer_command",
                        "data": {"action": "PAUSE"},
                        "timestamp": time.time(),
                        "expires_at": time.time() + 600,
                        "gid": f"overseer_exp_{int(time.time())}",
                    }
                    await self.crdt.add_genome(cmd_pause_explorer)
                    logger.info("🔎 Overseer: pausing Explorer")
        except Exception as e:
            logger.error(f"Overseer coordination failed: {e}", exc_info=True)

    def _get_resource_context(self) -> str:
        """
        Gathers system resource information (CPU, RAM, Disk) using psutil.
        Returns a formatted string describing current resource usage.
        """
        try:
            import psutil
            cpu: float = psutil.cpu_percent(interval=1)
            mem: Any = psutil.virtual_memory() # psutil.svmem is not typed by default, Any is suitable
            disk: Any = psutil.disk_usage('/') # psutil.sdiskusage is not typed by default, Any is suitable
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
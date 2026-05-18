#!/usr/bin/env python3
"""
Overseer Node – A strategic coordinator for Trade, Security, and Explorer swarms.
It analyzes heartbeats from all swarms and issues JSON commands via an LLM.
"""
import asyncio
import logging
import time
import sys
import uuid
import json
from typing import Dict, Any, List, Optional
import re

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

# Optional dependency for system resource monitoring
try:
    import psutil
except ImportError:
    psutil = None
    print("Warning: psutil not installed. System resource monitoring will be unavailable.", file=sys.stderr)

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("Overseer")

class OverseerNode:
    """
    OverseerNode acts as a strategic coordinator, analyzing heartbeats from Trade, Security,
    and Explorer swarms and issuing JSON commands via an LLM.
    """
    def __init__(self, node_id: Optional[str] = None) -> None:
        """
        Initializes the OverseerNode with a unique ID, LLM client, and CRDT adapter.

        Args:
            node_id: A unique identifier for the Overseer node. If None, a UUID-based ID is generated.
        """
        self.node_id: str = node_id or f"overseer-{uuid.uuid4().hex[:8]}"
        self.llm: LLMClient = LLMClient(n_ctx=8192)
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.step: int = 0

    async def run(self) -> None:
        """
        Starts the main loop for the OverseerNode.
        It periodically coordinates swarm activities based on a fixed step interval.
        """
        logger.info(f"🧭 Overseer {self.node_id} started")
        while True:
            self.step += 1
            # Coordinate every 150 seconds (2.5 minutes)
            if self.step % 150 == 0:
                logger.info(f"📈 Overseer step {self.step}: Initiating coordination cycle.")
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
            decisions: Dict[str, Any] = {} # Initialize decisions dictionary

            # --- Aggregate Trade Swarm Heartbeats ---
            # Heartbeats considered valid if received within the last 10 minutes (600 seconds).
            trade_hbs: List[Dict[str, Any]] = [
                v for v in all_state.values()
                if isinstance(v, dict) and v.get("type") == "trade_heartbeat"
                and (now - v.get("timestamp", 0) < 600)
            ]
            trade_nodes: int = len(set(h.get("node_id") for h in trade_hbs))
            trade_capital: float = sum(h.get("capital", 0.0) for h in trade_hbs)
            trade_dq: float = sum(h.get("dq", 0.0) for h in trade_hbs) / max(len(trade_hbs), 1)
            trade_fitness: float = sum(h.get("fitness", 0.0) for h in trade_hbs) / max(len(trade_hbs), 1)
            logger.debug(f"Trade swarm stats: Nodes={trade_nodes}, Capital={trade_capital:.0f}, DQ={trade_dq:.3f}, Fitness={trade_fitness:.3f}")

            # --- Check for Stale Trade Nodes ---
            # Nodes are considered stale if their heartbeat is older than 3 minutes (180 seconds).
            stale_nodes: List[str] = [
                h.get("node_id") for h in trade_hbs
                if (now - h.get("timestamp", 0) > 180)
            ]
            for node_id_stale in set(stale_nodes):
                logger.warning(f"🔄 Overseer: Detected stale trade node {node_id_stale}. Requesting restart.")
                cmd_restart: Dict[str, Any] = {
                    "type": "sec_command",
                    "data": {"action": "RESTART_NODE", "node_id": node_id_stale},
                    "timestamp": now,
                    "expires_at": now + 300, # Command expires in 5 minutes
                    "gid": f"overseer_restart_{int(now)}_{node_id_stale}",
                }
                await self.crdt.add_genome(cmd_restart)

            # --- Aggregate Security Swarm Heartbeats ---
            sec_hbs: List[Dict[str, Any]] = [
                v for v in all_state.values()
                if isinstance(v, dict) and v.get("type") == "security_heartbeat"
                and (now - v.get("timestamp", 0) < 600)
            ]
            sec_nodes: int = len(set(h.get("node_id") for h in sec_hbs))
            blocked_ips: int = sum(h.get("blocked_ips", 0) for h in sec_hbs)
            logger.debug(f"Security swarm stats: Nodes={sec_nodes}, Blocked IPs={blocked_ips}")

            # --- Check for Security Vulnerability Alerts ---
            vuln_alerts: List[Dict[str, Any]] = [
                v for v in all_state.values()
                if isinstance(v, dict) and v.get("type") == "vulnerability_alert"
            ]
            if vuln_alerts:
                logger.warning("🔴 Overseer: Vulnerabilities detected. Forcing 'reduce_risk' decision.")
                decisions["reduce_risk"] = True # Force this decision

            # --- Aggregate Explorer Swarm Heartbeats and Findings ---
            exp_hbs: List[Dict[str, Any]] = [
                v for v in all_state.values()
                if isinstance(v, dict) and v.get("type") == "explorer_heartbeat"
                and (now - v.get("timestamp", 0) < 600)
            ]
            exp_nodes: int = len(set(h.get("node_id") for h in exp_hbs))
            findings: int = len([
                v for v in all_state.values()
                if isinstance(v, dict) and v.get("type") == "explorer_finding"
            ])
            logger.debug(f"Explorer swarm stats: Nodes={exp_nodes}, Findings={findings}")

            resources: str = self._get_resource_context()

            # --- Construct LLM Prompt for Strategic Decision Making ---
            prompt: str = f"""User: You are BlackSwan Overseer, a strategic coordinator for three swarms:
- Trade swarm: {trade_nodes} nodes, total capital {trade_capital:.0f}, DQ {trade_dq:.3f}, fitness {trade_fitness:.3f}
- Security swarm: {sec_nodes} nodes, {blocked_ips} IPs blocked
- Explorer swarm: {exp_nodes} nodes, {findings} findings
- System resources: {resources}

Decide:
1. Should you reduce trade risk? (if DQ > 0.25 or capital < 2000, answer YES)
2. Should you increase exploration? (if fitness is high and DQ is low, answer YES)
3. Should you unblock all IPs? (if blocked IPs > 50, answer YES)
4. Should you spawn more nodes? (if RAM > 500MB free, answer YES)
5. Should the Explorer continue? (if findings > 100, answer NO)

Output ONLY a perfectly valid JSON object with these boolean fields: reduce_risk, increase_exploration, unblock_ips, spawn_nodes, continue_explorer.
Ensure the JSON is fully closed and correctly formatted.
Example: {{"reduce_risk":false,"increase_exploration":true,"unblock_ips":false,"spawn_nodes":false,"continue_explorer":true}}
Assistant: """ # The LLM will complete from here.
            
            logger.debug(f"Sending prompt to LLM: {prompt[:500]}...")
            response: str = self.llm.generate(prompt, max_tokens=120, temperature=0.1) # Increased max_tokens slightly
            logger.debug(f"Raw LLM response: {response}")

            if response:
                # --- Robust JSON Parsing from LLM Response ---
                # 1. Attempt to fix common LLM JSON errors:
                #    - Ensure the response starts and ends with curly braces if it's missing.
                if not response.strip().startswith('{'):
                    response = '{' + response.strip()
                if not response.strip().endswith('}'):
                    response = response.strip() + '}'

                #    - Add quotes to unquoted keys (e.g., `field: value` -> `"field": value`).
                #      This regex handles cases like `{"field":` or `{field:`
                cleaned_response = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', response)
                logger.debug(f"Cleaned LLM response (quotes added): {cleaned_response[:200]}")

                # 2. Extract the first complete JSON object using bracket balancing.
                candidate_json_str: Optional[str] = None
                start_brace = cleaned_response.find('{')
                if start_brace != -1:
                    depth = 0
                    for i in range(start_brace, len(cleaned_response)):
                        if cleaned_response[i] == '{':
                            depth += 1
                        elif cleaned_response[i] == '}':
                            depth -= 1
                        if depth == 0 and cleaned_response[i] == '}':
                            candidate_json_str = cleaned_response[start_brace : i + 1]
                            break
                
                if candidate_json_str:
                    try:
                        decisions_from_llm = json.loads(candidate_json_str)
                        # Ensure all expected keys are present and boolean
                        for key in ["reduce_risk", "increase_exploration", "unblock_ips", "spawn_nodes", "continue_explorer"]:
                            if key not in decisions_from_llm or not isinstance(decisions_from_llm[key], bool):
                                logger.warning(f"LLM decision missing or invalid type for '{key}'. Defaulting to False. Raw: {decisions_from_llm}")
                                decisions_from_llm[key] = False
                        decisions.update(decisions_from_llm) # Merge with any forced decisions (like from vuln_alerts)
                        logger.info(f"LLM decision parsed: {json.dumps(decisions)}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Overseer failed to parse LLM JSON: '{candidate_json_str}'. Error: {e}. Full response: '{response}'")
                else:
                    logger.warning(f"Overseer: No valid JSON object found in LLM response: '{response}'")
            else:
                logger.warning("Overseer: LLM returned an empty response.")
                return # Exit if no response to parse

            # --- Apply Decisions ---
            if decisions.get("reduce_risk"):
                cmd_reduce_risk: Dict[str, Any] = {
                    "type": "meta_command_json",
                    "data": {
                        "action": "ADJUST_SWARM",
                        "params": {
                            "exploration_multiplier": 1.0, # Reduce exploration
                            "risk_scale": 0.7,             # Scale down risk
                            "survival_bias_adj": 0.05,     # Prioritize survival
                            "stop_loss_adj": 0.8,          # Tighten stop loss
                            "confidence": 0.9              # High confidence in safety override
                        },
                        "reason": "Overseer safety override: Reducing trade risk due to high DQ, low capital, or vulnerabilities."
                    },
                    "timestamp": time.time(),
                    "expires_at": time.time() + 300,
                    "gid": f"overseer_reduce_risk_{int(time.time())}",
                }
                await self.crdt.add_genome(cmd_reduce_risk)
                logger.info("🧭 Overseer: Reducing trade risk.")

            if decisions.get("increase_exploration"):
                cmd_increase_exploration: Dict[str, Any] = {
                    "type": "meta_command_json",
                    "data": {
                        "action": "ADJUST_SWARM",
                        "params": {
                            "exploration_multiplier": 1.5, # Increase exploration
                            "risk_scale": 1.0,
                            "survival_bias_adj": 0.0,
                            "stop_loss_adj": 1.0,
                            "confidence": 0.8
                        },
                        "reason": "Overseer: Increasing exploration due to high fitness and low DQ."
                    },
                    "timestamp": time.time(),
                    "expires_at": time.time() + 300,
                    "gid": f"overseer_increase_exploration_{int(time.time())}",
                }
                await self.crdt.add_genome(cmd_increase_exploration)
                logger.info("🧭 Overseer: Increasing exploration.")

            if decisions.get("unblock_ips"):
                cmd_unblock_ips: Dict[str, Any] = {
                    "type": "sec_command",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": time.time(),
                    "expires_at": time.time() + 600, # Command expires in 10 minutes
                    "gid": f"overseer_sec_unblock_{int(time.time())}",
                }
                await self.crdt.add_genome(cmd_unblock_ips)
                logger.info("🔓 Overseer: Requesting unblock of all IPs.")

            if decisions.get("spawn_nodes"):
                logger.info("🧭 Overseer: Recommends spawning more nodes. (Action requires external orchestrator, e.g., Docker API).")
                # TODO: Implement automatic scaling via Docker API or similar orchestration tool.

            if decisions.get("continue_explorer") is False:
                cmd_pause_explorer: Dict[str, Any] = {
                    "type": "explorer_command",
                    "data": {"action": "PAUSE"},
                    "timestamp": time.time(),
                    "expires_at": time.time() + 600, # Command expires in 10 minutes
                    "gid": f"overseer_exp_pause_{int(time.time())}",
                }
                await self.crdt.add_genome(cmd_pause_explorer)
                logger.info("🔎 Overseer: Pausing Explorer swarm activities.")

        except Exception as e:
            logger.error(f"Overseer coordination failed: {e}", exc_info=True)

    def _get_resource_context(self) -> str:
        """
        Gathers system resource information (CPU, RAM, Disk) using psutil.
        Returns a formatted string describing current resource usage.
        If psutil is not available, returns a message indicating so.
        """
        if psutil is None:
            return "Resource data unavailable (psutil not installed)"
        try:
            cpu: float = psutil.cpu_percent(interval=None) # Non-blocking call for current CPU usage
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            return (
                f"CPU: {cpu:.1f}%, RAM: {mem.percent:.1f}% ({mem.available // (1024*1024)}MB free), "
                f"Disk: {disk.percent:.1f}% ({disk.free // (1024*1024)}MB free)"
            )
        except Exception as e:
            logger.warning(f"Resource check failed: {e}")
            return f"Resource check failed: {e}"

if __name__ == "__main__":
    node = OverseerNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("Overseer stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Overseer encountered a fatal error: {e}", exc_info=True)

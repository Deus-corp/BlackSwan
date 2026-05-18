#!/usr/bin/env python3
"""
Security MetaAgent – анализирует угрозы и управляет роем безопасности.

This agent acts as a centralized intelligence for the security swarm. It
periodically reflects on the overall security state reported by individual
security nodes (via CRDT) and makes high-level decisions, such as unblocking
all IPs if conditions warrant.
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, Any, List, Optional

# Assuming 'src' and 'mvp/lab_swarm_demo' are in PYTHONPATH or the script
# is run from the project root.
from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

# Configure logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("SecurityMetaAgent")

# Constants for better readability and maintainability
REFLECTION_INTERVAL_STEPS: int = 100
MAIN_LOOP_SLEEP_SECONDS: float = 1.0
UNBLOCK_COMMAND_EXPIRATION_SECONDS: int = 600
LLM_MAX_TOKENS: int = 10
LLM_TEMPERATURE: float = 0.1

class SecurityMetaAgent:
    """
    SecurityMetaAgent analyzes threats and manages the security swarm.
    It periodically reflects on the overall security state via CRDT and issues commands.
    """
    def __init__(self, node_id: Optional[str] = None) -> None:
        """
        Initializes the SecurityMetaAgent with a unique ID, LLM client, and CRDT adapter.

        Args:
            node_id: A unique identifier for this agent instance. If None, one will be generated.
        """
        self.node_id: str = node_id or f"sec-meta-{uuid.uuid4().hex[:8]}"
        # LLM client with a defined context window
        self.llm: LLMClient = LLMClient(n_ctx=4096)
        # CRDT adapter for distributed state synchronization
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        # Internal step counter for scheduling periodic tasks
        self.step: int = 0

    async def run(self) -> None:
        """
        Starts the main loop for the SecurityMetaAgent, periodically reflecting on security state.
        The agent will run indefinitely until interrupted.
        """
        logger.info(f"🔐 SecurityMetaAgent {self.node_id} started")
        try:
            while True:
                self.step += 1
                # Periodically reflect on the security state
                if self.step % REFLECTION_INTERVAL_STEPS == 0:
                    await self.reflect()
                await asyncio.sleep(MAIN_LOOP_SLEEP_SECONDS)
        except asyncio.CancelledError:
            logger.info(f"SecurityMetaAgent {self.node_id} run cancelled.")
        except Exception as e:
            logger.exception(f"SecurityMetaAgent {self.node_id} encountered a critical error: {e}")

    async def reflect(self) -> None:
        """
        Reflects on the current security state by checking heartbeats from security nodes
        and uses an LLM to decide on actions, such as unblocking all IPs.
        """
        logger.debug(f"SecurityMetaAgent {self.node_id} reflecting at step {self.step}...")
        try:
            # Retrieve the full state from CRDT
            all_state: Dict[str, Any] = self.crdt.state
            # Filter for security heartbeat messages
            heartbeats: List[Dict[str, Any]] = [
                v for k, v in all_state.items()
                if isinstance(v, dict) and v.get("type") == "security_heartbeat"
            ]
            # Aggregate the number of blocked IPs reported by nodes
            blocked_ips_count: int = sum(h.get("blocked_ips", 0) for h in heartbeats)

            # Construct the prompt for the LLM
            prompt: str = (
                f"User: You are a cybersecurity AI. Swarm status: {len(heartbeats)} nodes reporting, "
                f"{blocked_ips_count} IPs blocked. Do you recommend unblocking all IPs? "
                "Answer ONLY 'YES' or 'NO'.\nAssistant: "
            )
            
            # Generate response from LLM
            response: str = self.llm.generate(
                prompt, max_tokens=LLM_MAX_TOKENS, temperature=LLM_TEMPERATURE
            )
            
            # Process LLM's recommendation
            if response and "YES" in response.upper():
                cmd: Dict[str, Any] = {
                    "type": "sec_command",
                    "data": {"action": "UNBLOCK_ALL"},
                    "timestamp": time.time(),
                    "expires_at": time.time() + UNBLOCK_COMMAND_EXPIRATION_SECONDS,
                    "gid": f"sec_cmd_{int(time.time())}", # Unique ID for the command
                }
                await self.crdt.add_genome(cmd)
                logger.info("🔓 SecurityMetaAgent: Recommended unblocking all IPs and issued command.")
            else:
                logger.debug(f"SecurityMetaAgent: LLM did not recommend unblocking. Response: '{response}'")

        except Exception as e:
            logger.error(f"SecurityMetaAgent reflection failed: {e}", exc_info=True)

if __name__ == "__main__":
    node = SecurityMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("SecurityMetaAgent stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"SecurityMetaAgent encountered an unexpected error during startup or main loop: {e}", exc_info=True)
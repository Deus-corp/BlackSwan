#!/usr/bin/env python3
"""
Explorer MetaAgent – анализирует находки и предлагает новые цели.
"""
import asyncio, logging, os, sys, time, uuid, json
from typing import Dict, Any, List, Optional

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("ExplorerMetaAgent")

class ExplorerMetaAgent:
    """
    Explorer MetaAgent analyzes findings from ExplorerNode agents and suggests new targets.
    It uses an LLM to classify web findings (USEFUL, HARMFUL, NEUTRAL) and
    generates new URLs based on useful findings, publishing them to the CRDT.
    """
    def __init__(self):
        """
        Initializes the ExplorerMetaAgent with a unique node ID,
        an LLM client configured for smaller contexts, and a CRDT adapter.
        """
        self.node_id: str = f"exp-meta-{uuid.uuid4().hex[:8]}"
        self.llm: LLMClient = LLMClient(n_ctx=2048)   # поменьше, чтобы не нагружать
        self.crdt: CRDTAdapter = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.step: int = 0

    async def run(self) -> None:
        """
        Runs the main operational loop of the ExplorerMetaAgent.
        It periodically calls the `reflect` method to process findings and suggest new targets.
        """
        logger.info(f"🔎 ExplorerMetaAgent {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 100 == 0:
                await self.reflect()
            await asyncio.sleep(1.0)

    async def reflect(self) -> None:
        """
        Performs the reflection process, which involves:
        1. Retrieving all "explorer_finding" entries from the CRDT.
        2. Classifying a subset of these findings using the LLM into categories
           like USEFUL, HARMFUL, or NEUTRAL, and updating their classification in CRDT.
        3. Generating new related URLs based on "USEFUL" findings using the LLM.
        4. Publishing these newly suggested URLs as "explorer_targets" to the CRDT.
        Error handling is included to catch issues during LLM interaction or CRDT updates.
        """
        try:
            all_state: Dict[str, Any] = self.crdt.state
            findings: List[Dict[str, Any]] = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "explorer_finding"]
            if not findings:
                return
            # Классифицируем находки через LLM
            for f in findings[:5]:   # не больше 5 за цикл
                content: str = f.get("content_preview", "")
                url: str = f.get("url", "")
                prompt: str = f"""User: Classify this web finding from {url}. Content preview: {content}
Categories: USEFUL, HARMFUL, NEUTRAL. Output ONLY one word.
Assistant: """
                response: Optional[str] = self.llm.generate(prompt, max_tokens=10, temperature=0.2)
                if response:
                    classification: str = response.strip().upper()
                    if classification in ("USEFUL", "HARMFUL", "NEUTRAL"):
                        f["classification"] = classification
                        await self.crdt.add_genome(f)   # обновляем в CRDT
            # Генерируем новые URL на основе полезных находок
            useful: List[Dict[str, Any]] = [f for f in findings if f.get("classification") == "USEFUL"]
            if useful:
                # Filter for non-None URLs before joining
                url_list: List[str] = [f_url for f in useful[:3] if (f_url := f.get("url")) is not None]
                if not url_list:
                    return # No URLs to base new suggestions on

                prompt: str = f"User: Based on these useful URLs: {', '.join(url_list)}. Suggest 2 new related URLs. Output ONLY JSON with 'urls' array.\nAssistant: {{"
                response = self.llm.generate(prompt, max_tokens=80, temperature=0.3)
                if response:
                    start: int = response.find('{')
                    end: int = response.rfind('}')
                    if start != -1 and end != -1:
                        candidate: str = response[start:end+1]
                        try:
                            data: Dict[str, Any] = json.loads(candidate)
                        except json.JSONDecodeError: # More specific exception for JSON parsing
                            try:
                                data = json.loads(candidate + "}") # Attempt to fix truncated JSON
                            except json.JSONDecodeError: # More specific exception
                                return
                        if "urls" in data and isinstance(data["urls"], list):
                            cmd: Dict[str, Any] = {
                                "type": "explorer_targets",
                                "data": {"urls": data["urls"]},
                                "timestamp": time.time(),
                                "gid": f"exp_cmd_{int(time.time())}",
                            }
                            await self.crdt.add_genome(cmd)
                            logger.info(f"🔎 ExplorerMetaAgent suggested URLs: {data['urls']}")
        except Exception as e:
            logger.error(f"ExplorerMetaAgent reflection failed: {e}")

if __name__ == "__main__":
    node: ExplorerMetaAgent = ExplorerMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerMetaAgent stopped.")
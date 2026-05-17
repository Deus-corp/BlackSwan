#!/usr/bin/env python3
"""
Explorer MetaAgent – анализирует находки и предлагает новые цели.
"""
import asyncio, logging, os, sys, time, uuid, json
from typing import Dict, Any, List

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("ExplorerMetaAgent")

class ExplorerMetaAgent:
    def __init__(self):
        self.node_id = f"exp-meta-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient(n_ctx=2048)   # поменьше, чтобы не нагружать
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        self.step = 0

    async def run(self):
        logger.info(f"🔎 ExplorerMetaAgent {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 100 == 0:
                await self.reflect()
            await asyncio.sleep(1.0)

    async def reflect(self):
        try:
            all_state = self.crdt.state
            findings = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "explorer_finding"]
            if not findings:
                return
            prompt = f"User: {len(findings)} web findings. Suggest 1-3 new URLs to explore. Output ONLY a JSON with 'urls' array. Example: {{\"urls\":[\"https://example.com\"]}}\nAssistant: {{"
            response = self.llm.generate(prompt, max_tokens=80, temperature=0.3)
            if response:
                start = response.find('{')
                end = response.rfind('}')
                if start != -1 and end != -1:
                    candidate = response[start:end+1]
                    try:
                        data = json.loads(candidate)
                    except:
                        try:
                            data = json.loads(candidate + "}")
                        except:
                            return
                    if "urls" in data:
                        cmd = {
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
    node = ExplorerMetaAgent()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("ExplorerMetaAgent stopped.")
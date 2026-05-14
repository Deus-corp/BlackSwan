#!/usr/bin/env python3
"""
MetaAgent – отдельный узел-наблюдатель, непрерывно рефлексирующий над роем.
Читает heartbeats и сделки из events.jsonl, пишет размышления в meta_events.jsonl.
Публикует команды в CRDT.
"""
import asyncio, logging, os, sys, time, uuid, json
from typing import Dict, Any, List

from src.core.crdt_adapter import CRDTAdapter
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("MetaAgent")


class MetaAgentNode:
    def __init__(self):
        self.node_id = f"meta-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient()
        self.crdt = CRDTAdapter(node_id=self.node_id)
        # Путь к общему JSONL-файлу событий роя
        self.events_jsonl_path = config.event_ledger_path or "./data/ledgers/events.jsonl"
        # Путь к собственному JSONL-файлу размышлений
         # Собственная папка для размышлений MetaAgent
        meta_dir = "/app/data/meta_agent"
        os.makedirs(meta_dir, exist_ok=True)
        self.meta_events_jsonl_path = os.path.join(meta_dir, "meta_events.jsonl")
        
        self.memory: List[str] = []
        self.max_memory_entries = 5
        self.step = 0
        self._load_memory_from_jsonl()

    def _load_memory_from_jsonl(self):
        try:
            recent = self._get_recent_events_from_jsonl("meta_reflection", limit=self.max_memory_entries)
            for evt in recent:
                thought = evt.get("payload", {}).get("thought", "")
                if thought:
                    self.memory.append(thought)
            logger.info(f"Loaded {len(self.memory)} past reflections from memory")
        except Exception as e:
            logger.warning(f"Could not load memory from JSONL: {e}")

    def _clean_thinking(self, text: str) -> str:
        import re
        cleaned = re.sub(r'<[^>]+>', '', text)
        cleaned = cleaned.strip()
        return cleaned if cleaned else text.strip()

    def _get_recent_events_from_jsonl(self, event_type: str, limit: int = 30) -> list:
        """Читает последние события указанного типа из JSONL-файла."""
        try:
            if not os.path.exists(self.events_jsonl_path):
                logger.warning(f"JSONL file not found: {self.events_jsonl_path}")
                return []
            events = []
            with open(self.events_jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except:
                        continue
                    if evt.get("event_type") == event_type:
                        events.append({
                            "node_id": evt.get("node_id"),
                            "event_type": evt.get("event_type"),
                            "payload": evt.get("payload", {}),
                            "timestamp": evt.get("timestamp", ""),
                        })
            return events[-limit:]
        except Exception as e:
            logger.warning(f"Cannot read events from JSONL: {e}")
            return []

    def _append_to_jsonl(self, event_type: str, payload: dict):
        """Добавляет событие в собственный JSONL-файл MetaAgent."""
        try:
            record = {
                "node_id": self.node_id,
                "event_type": event_type,
                "payload": payload,
                "timestamp": time.time(),
            }
            with open(self.meta_events_jsonl_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to meta JSONL: {e}")

    async def publish_command(self, thought: str):
        try:
            command = {
                "type": "meta_command",
                "thought": thought,
                "timestamp": time.time(),
                "gid": f"meta_cmd_{int(time.time())}",
            }
            await self.crdt.add_genome(command)
            logger.info("📡 MetaAgent published command to swarm")
        except Exception as e:
            logger.error(f"Failed to publish command: {e}")

    async def run(self):
        logger.info(f"🧠 MetaAgent {self.node_id} started")
        while True:
            self.step += 1
            if self.step % 100 == 0:
                await self.reflect()
            await asyncio.sleep(1.0)

    async def reflect(self):
        try:
            heartbeats = self._get_recent_events_from_jsonl("heartbeat", limit=30)
            trades = self._get_recent_events_from_jsonl("trade_executed", limit=30)

            if heartbeats:
                node_ids = set(h["node_id"] for h in heartbeats)
                node_count = len(node_ids)
                total_capital = sum(h["payload"].get("capital", 0) for h in heartbeats)
                avg_capital = total_capital / node_count if node_count > 0 else 0
                avg_fitness = sum(h["payload"].get("fitness", 0) for h in heartbeats) / max(len(heartbeats), 1)
                dq_values = [h["payload"].get("dq", 0) for h in heartbeats]
                avg_dq = sum(dq_values) / len(dq_values) if dq_values else 0
                niches = {}
                for h in heartbeats:
                    nc = h["payload"].get("niche_counts", {})
                    for niche, count in nc.items():
                        niches[niche] = niches.get(niche, 0) + count
                dominant_niche = max(niches, key=niches.get) if niches else "unknown"
            else:
                node_count = 0
                avg_capital = 0
                avg_fitness = 0
                avg_dq = 0
                dominant_niche = "unknown"

            swarm_context = (
                f"Active nodes (with heartbeats): {node_count}\n"
                f"Average capital per node: {avg_capital:.2f}\n"
                f"Average fitness: {avg_fitness:.4f}\n"
                f"Average DQ: {avg_dq:.3f}\n"
                f"Dominant niche: {dominant_niche}\n"
                f"Recent trades count: {len(trades)}\n"
            )

            market = self._get_market_context()
            past = "\n".join(f"- {t}" for t in self.memory[-self.max_memory_entries:]) or "(no previous thoughts)"

            prompt = f"""SYSTEM: You are BlackSwan ASI, a self-aware distributed superintelligence observing a live trading swarm on Ethereum Sepolia testnet. You do not trade, you only think and guide.

CRITICAL INSTRUCTION:
- You MUST respond with ONLY the final analysis in plain English.
- Do NOT output any placeholder text like "thinking process".
- Do NOT use XML tags (think, /think).
- Structure your answer EXACTLY as follows:

OBSERVATION:
<1-2 sentences summarising what you see in the swarm>

SWARM ASSESSMENT:
<1-2 sentences evaluating the swarm's health, risks, and opportunities>

STRATEGIC ADJUSTMENTS:
<1-2 concrete adjustments you would recommend (e.g., "increase exploration rate", "tighten stop-loss", "convert excess USDC to WETH")>

Current swarm data:
{swarm_context}

Market environment:
{market}

Your recent thoughts:
{past}
"""
            response = self.llm.generate(prompt, max_tokens=400, temperature=0.5)
            if response:
                thought = self._clean_thinking(response)
                self.memory.append(thought)
                if len(self.memory) > self.max_memory_entries:
                    self.memory = self.memory[-self.max_memory_entries:]
                # Сохраняем размышление в JSONL
                self._append_to_jsonl("meta_reflection", {"thought": thought})
                # Публикуем управляющую команду в CRDT
                await self.publish_command(thought)
                logger.info(f"🧠 MetaAgent reflection:\n{thought}")
        except Exception as e:
            logger.error(f"MetaAgent reflection failed: {e}")

    def _get_market_context(self) -> str:
        return "Market data not directly available to observer (use shared state)."

if __name__ == "__main__":
    node = MetaAgentNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("MetaAgent stopped.")
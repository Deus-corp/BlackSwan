#!/usr/bin/env python3
"""
MetaAgent – отдельный узел-наблюдатель, непрерывно рефлексирующий над роем.
Не торгует, только анализирует состояние через CRDT, event_store и LLM.
"""
import asyncio, logging, os, sys, time, uuid, json, sqlite3
from typing import Dict, Any, List

from src.core.crdt_adapter import CRDTAdapter
from src.core.event_store import EventStore
from src.core.events import Event
from src.intelligence.llm_client import LLMClient
from swarm_config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s')
logger = logging.getLogger("MetaAgent")


class MetaAgentNode:
    def __init__(self):
        self.node_id = f"meta-{uuid.uuid4().hex[:8]}"
        self.llm = LLMClient()
        self.crdt = CRDTAdapter(node_id=self.node_id)
        self.event_store = EventStore(
            ledger_path=config.event_ledger_path,
            sqlite_path=config.event_sqlite_path,
        )
        self.memory: List[str] = []
        self.max_memory_entries = 5
        self.step = 0
        self._load_memory_from_db()

    def _load_memory_from_db(self):
        """Загружает последние размышления из event_store при старте."""
        try:
            recent = self._get_recent_events("meta_reflection", limit=self.max_memory_entries)
            for evt in recent:
                thought = evt.get("payload", {}).get("thought", "")
                if thought:
                    self.memory.append(thought)
            logger.info(f"Loaded {len(self.memory)} past reflections from memory")
        except Exception as e:
            logger.warning(f"Could not load memory from DB: {e}")

    def _clean_thinking(self, text: str) -> str:
        """
        Удаляет из ответа модели блоки  think ...  think  и любые другие XML-теги.
        """
        import re
        # Удаляем всё, что похоже на XML-теги
        cleaned = re.sub(r'<[^>]+>', '', text)
        cleaned = cleaned.strip()
        # Если после очистки осталась пустая строка, возвращаем исходный текст (без тегов)
        return cleaned if cleaned else text.strip()

    def _get_recent_events(self, event_type: str, limit: int = 20) -> list:
        """Читает последние события указанного типа из event_store (SQLite)."""
        try:
            db_path = self.event_store.sqlite_path
            if not os.path.exists(db_path):
                logger.warning(f"Event store DB not found at {db_path}")
                return []
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            # Схема EventStore: (id, node_id, event_type, payload, parent_id, timestamp)
            cur = conn.execute(
                "SELECT node_id, event_type, payload, timestamp FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                (event_type, limit)
            )
            rows = cur.fetchall()
            conn.close()
            events = []
            for r in reversed(rows):
                try:
                    payload = json.loads(r["payload"])
                except:
                    payload = {}
                events.append({
                    "node_id": r["node_id"],
                    "event_type": r["event_type"],
                    "payload": payload,
                    "timestamp": r["timestamp"],
                })
            return events
        except Exception as e:
            logger.warning(f"Cannot read events from event_store: {e}")
            return []

    async def publish_command(self, thought: str):
        """
        Публикует управляющую рекомендацию в CRDT.
        """
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
            if self.step % 300 == 0:
                await self.reflect()
            await asyncio.sleep(1.0)

    async def reflect(self):
        try:
            # 1. Читаем последние heartbeats и сделки
            heartbeats = self._get_recent_events("heartbeat", limit=30)
            trades = self._get_recent_events("trade_executed", limit=30)

            # 2. Агрегируем статистику
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
                # Сохраняем в собственный event_store
                self.event_store.append(Event.create(
                    node_id=self.node_id,
                    event_type="meta_reflection",
                    payload={"thought": thought, "timestamp": time.time()},
                    parent_id=None,
                ))
                # Публикуем управляющую команду в CRDT для роя
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
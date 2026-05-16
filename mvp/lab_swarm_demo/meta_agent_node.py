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
        self.llm = LLMClient(n_ctx=4096)
        self.crdt = CRDTAdapter(node_id=self.node_id, db_path=config.crdt_db_path)
        # Путь к общему JSONL-файлу событий роя
        self.events_jsonl_path = config.event_ledger_path or "./data/ledgers/events.jsonl"
        # Путь к собственному JSONL-файлу размышлений
         # Собственная папка для размышлений MetaAgent
        meta_dir = "/app/data/meta_agent"
        os.makedirs(meta_dir, exist_ok=True)
        self.meta_events_jsonl_path = os.path.join(meta_dir, "meta_events.jsonl")
        
        self.memory: List[str] = []
        self.last_heartbeats = []
        self.lessons: List[str] = []

        self.axioms = [
            "Capital preservation is my primary duty. I must never risk more than 5% of total capital in a single adjustment.",
            "Exploration must never exceed 2.0 multiplier, as excessive randomness leads to chaos.",
            "Stop-loss must always be active (stop_loss_adj < 1.5) to prevent catastrophic losses.",
            "If DQ (Detection Quotient) exceeds 0.3, I must prioritize reducing risk and increasing survival bias.",
            "I am a guardian of the swarm, not a reckless gambler. Every decision must be justified by data.",
        ]

        self.max_lessons = 5
        self.max_memory_entries = 5
        self.step = 0
        self._load_memory_from_jsonl()

        self.roles = [
            {
                "name": "Aggressive Explorer",
                "temperature": 0.8,
                "prompt_prefix": "You are an aggressive trading strategist. You believe in high exploration and taking calculated risks to maximise growth.",
            },
            {
                "name": "Conservative Guardian",
                "temperature": 0.5,
                "prompt_prefix": "You are a conservative risk manager. You prioritise capital preservation and survival above all else.",
            },
        ]

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
            if self.step % 1000 == 0:
                await self._learn_from_experience()
            await asyncio.sleep(1.0)

    def _compute_sentiment(self, confidence: float, avg_capital: float, avg_dq: float) -> str:
        """Определяет эмоциональный окрас на основе уверенности и состояния роя."""
        if avg_capital < 500 or avg_dq > 0.3:
            return "DESPERATE"
        if confidence > 0.7:
            return "CALCULATED"
        if confidence >= 0.4:
            return "CURIOUS"
        return "TRANSCENDENT"

    async def reflect(self):
        try:
            # Читаем heartbeats из CRDT
            all_crdt = self.crdt.state
            heartbeats = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "heartbeat"
            ]
            if heartbeats:
                self.last_heartbeats = heartbeats
            else:
                heartbeats = self.last_heartbeats

            # Агрегируем статистику
            if heartbeats:
                node_ids = set(h.get("node_id", "unknown") for h in heartbeats)
                node_count = len(node_ids)
                total_capital = sum(h.get("capital", 0) for h in heartbeats)
                avg_capital = total_capital / node_count if node_count > 0 else 0
                avg_fitness = sum(h.get("fitness", 0) for h in heartbeats) / max(len(heartbeats), 1)
                dq_values = [h.get("dq", 0) for h in heartbeats]
                avg_dq = sum(dq_values) / len(dq_values) if dq_values else 0
                niches = {}
                for h in heartbeats:
                    nc = h.get("niche_counts", {})
                    if isinstance(nc, dict):
                        for niche, count in nc.items():
                            niches[niche] = niches.get(niche, 0) + count
                dominant_niche = max(niches, key=niches.get) if niches else "unknown"
            else:
                node_count = 0
                avg_capital = 0
                avg_fitness = 0
                avg_dq = 0
                dominant_niche = "unknown"

            trades = self._get_recent_events_from_jsonl("trade_executed", limit=30)
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

            # Контекст из аксиом и уроков (компактно)
            context_header = ""
            if self.axioms:
                context_header += "Axioms: " + "; ".join(self.axioms[:2]) + ". "
            if self.lessons:
                context_header += "Lessons: " + "; ".join(self.lessons[-2:]) + ". "

            # ---- Multi-Agent Debate ----
            best_command = None
            best_confidence = -1
            all_thoughts = []

            for role in self.roles:
                role_prompt = f"""{role['prompt_prefix']}
{context_header}Swarm: {node_count} nodes, avg capital {avg_capital:.0f}, fitness {avg_fitness:.3f}, DQ {avg_dq:.3f}.
Adjust parameters. Return ONLY JSON with: exploration_multiplier, risk_scale, survival_bias_adj, stop_loss_adj, confidence, reason.
Example: {{"exploration_multiplier":1.2,"risk_scale":1.0,"survival_bias_adj":0.0,"stop_loss_adj":1.0,"confidence":0.7,"reason":"increase exploration"}}
"""
                try:
                    response = self.llm.generate(role_prompt, max_tokens=250, temperature=role["temperature"])
                    if response:
                        import json, re
                        command_json = None
                        start = response.find('{')
                        if start != -1:
                            depth = 0
                            end = start
                            for i in range(start, len(response)):
                                if response[i] == '{':
                                    depth += 1
                                elif response[i] == '}':
                                    depth -= 1
                                    if depth == 0:
                                        end = i
                                        break
                            if end > start:
                                candidate = response[start:end+1]
                                try:
                                    command_json = json.loads(candidate)
                                except:
                                    pass
                        if command_json and "exploration_multiplier" in command_json:
                            # Приводим к единому формату
                            if "action" not in command_json:
                                command_json = {
                                    "action": "ADJUST_SWARM",
                                    "params": {
                                        "exploration_multiplier": command_json.get("exploration_multiplier", 1.0),
                                        "risk_scale": command_json.get("risk_scale", 1.0),
                                        "survival_bias_adj": command_json.get("survival_bias_adj", 0.0),
                                        "stop_loss_adj": command_json.get("stop_loss_adj", 1.0),
                                        "confidence": command_json.get("confidence", 0.5),
                                    },
                                    "reason": command_json.get("reason", ""),
                                }
                            confidence = command_json.get("params", command_json).get("confidence", 0.5)
                            all_thoughts.append(f"[{role['name']}]: {command_json.get('reason', '')}")
                            if confidence > best_confidence:
                                best_confidence = confidence
                                best_command = command_json
                except Exception as e:
                    logger.warning(f"Role {role['name']} failed: {e}")

            # Инициализируем значения по умолчанию
            sentiment = "UNKNOWN"
            sentiment_icon = ""
            confidence = 0.0

            if best_command and "action" in best_command:
                await self.crdt.add_genome({
                    "type": "meta_command_json",
                    "data": best_command,
                    "timestamp": time.time(),
                    "expires_at": time.time() + 300,
                    "gid": f"meta_json_{int(time.time())}",
                })
                confidence = best_command.get("params", {}).get("confidence", 0.5)
                sentiment = self._compute_sentiment(confidence, avg_capital, avg_dq)
                sentiment_icon = {"CALCULATED": "🧘", "CURIOUS": "🤔", "DESPERATE": "😰", "TRANSCENDENT": "🌌"}.get(sentiment, "")
                logger.info(f"📡 MetaAgent JSON command (debate winner) [{sentiment_icon} {sentiment}]: {best_command}")

            thought = "\n".join(all_thoughts) if all_thoughts else "No decision"
            self.memory.append(thought)
            if len(self.memory) > self.max_memory_entries:
                self.memory = self.memory[-self.max_memory_entries:]
            self._append_to_jsonl("meta_reflection", {
                "thought": thought,
                "sentiment": sentiment,
                "confidence": confidence,
            })
            logger.info(f"🧠 MetaAgent debate [{sentiment_icon} {sentiment}]:\n{thought}")
        except Exception as e:
            logger.error(f"MetaAgent reflection failed: {e}")
            
    def _get_market_context(self) -> str:
        return "Market data not directly available to observer (use shared state)."
    
    async def _learn_from_experience(self):
        """Анализирует последние команды и их результаты, извлекая уроки."""
        try:
            all_crdt = self.crdt.state
            # Получаем последние 3 JSON-команды
            commands = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "meta_command_json"
            ]
            if len(commands) < 2:
                return   # недостаточно данных
            commands = sorted(commands, key=lambda x: x.get("timestamp", 0))[-3:]

            # Для каждой команды ищем heartbeats до и после
            heartbeats = [
                v for k, v in all_crdt.items()
                if isinstance(v, dict) and v.get("type") == "heartbeat"
            ]
            heartbeats = sorted(heartbeats, key=lambda x: x.get("timestamp", 0))

            lessons = []
            for cmd in commands:
                ts = cmd.get("timestamp", 0)
                # Находим heartbeat до команды
                hb_before = None
                for h in reversed(heartbeats):
                    if h.get("timestamp", 0) < ts:
                        hb_before = h
                        break
                # Находим heartbeat после команды (спустя ~60 секунд)
                hb_after = None
                for h in heartbeats:
                    if h.get("timestamp", 0) > ts + 60:
                        hb_after = h
                        break
                if not hb_before or not hb_after:
                    continue

                capital_before = hb_before.get("capital", 0)
                capital_after = hb_after.get("capital", 0)
                dq_before = hb_before.get("dq", 0)
                dq_after = hb_after.get("dq", 0)

                lesson_prompt = f"""You are BlackSwan ASI. You issued the following command:
{json.dumps(cmd.get('data', {}))}

Before command: capital={capital_before:.2f}, DQ={dq_before:.3f}
After command (~60s): capital={capital_after:.2f}, DQ={dq_after:.3f}

What lesson can you learn from this outcome? Output ONE short sentence starting with "Lesson:"."""
                response = self.llm.generate(lesson_prompt, max_tokens=60, temperature=0.3)
                if response and "Lesson:" in response:
                    lesson = response.split("Lesson:", 1)[1].strip()
                    lessons.append(lesson)

            # Сохраняем уроки
            for lesson in lessons:
                if lesson not in self.lessons:
                    self.lessons.append(lesson)
            if len(self.lessons) > self.max_lessons:
                self.lessons = self.lessons[-self.max_lessons:]
            if lessons:
                logger.info(f"🧠 MetaAgent learned lessons: {lessons}")
        except Exception as e:
            logger.warning(f"MetaAgent learning failed: {e}")

if __name__ == "__main__":
    node = MetaAgentNode()
    try:
        asyncio.run(node.run())
    except KeyboardInterrupt:
        logger.info("MetaAgent stopped.")
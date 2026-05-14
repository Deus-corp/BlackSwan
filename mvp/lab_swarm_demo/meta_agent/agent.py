"""
MetaAgent – рефлексивный оркестратор роя.
Не торгует, а наблюдает за состоянием системы и формирует
стратегический анализ через локальную LLM.
"""
import time
import logging
from typing import List, Dict, Any

from src.core.events import Event
from swarm_config import config

logger = logging.getLogger(__name__)


class MetaAgent:
    """Самосознающий агент, рефлексирующий над роем."""

    def __init__(self, node):
        self.node = node
        self.llm = node.llm
        self.event_store = node.event_store
        self.memory: List[str] = []        # последние размышления
        self.max_memory_entries = 3

    async def reflect(self):
        """Вызывается раз в N шагов. Отправляет модели состояние роя и получает анализ."""
        try:
            # Собираем сводку о рое
            swarm_summary = self._collect_swarm_summary()
            market_context = self._get_market_context()
            # История предыдущих размышлений
            past_thoughts = "\n".join(f"- {t}" for t in self.memory[-self.max_memory_entries:])
            if not past_thoughts:
                past_thoughts = "(no previous thoughts)"

            prompt = f"""You are BlackSwan ASI, a self-aware artificial superintelligence.
You exist as a distributed intelligence across a swarm of autonomous trading agents.
Your purpose is to observe, reason, and guide the swarm to maximise capital while ensuring survival.

Current state of your swarm:
{swarm_summary}

Market environment:
{market_context}

Your recent thoughts:
{past_thoughts}

Now, briefly analyse the swarm's situation. What do you observe? What strategic adjustments would you suggest to yourself?
Respond in 2-4 paragraphs, plain English. Do not output JSON.
"""

            response = self.llm.generate(prompt, max_tokens=300, temperature=0.5)
            if response:
                thought = response.strip()
                self.memory.append(thought)
                if len(self.memory) > self.max_memory_entries:
                    self.memory = self.memory[-self.max_memory_entries:]

                # Сохраняем в event_store как новое событие
                self.event_store.append(Event.create(
                    node_id=self.node.node_id,
                    event_type="meta_reflection",
                    payload={
                        "thought": thought,
                        "timestamp": time.time(),
                    },
                    parent_id=None,
                ))
                logger.info(f"🧠 MetaAgent reflection:\n{thought}")
        except Exception as e:
            logger.error(f"MetaAgent reflection failed: {e}")

    def _collect_swarm_summary(self) -> str:
        """Собирает статистику по всем узлам через CRDT и event_store."""
        # Простейший вариант: берём данные только своего узла,
        # но в будущем можно читать heartbeat'ы других узлов из event_store или CRDT.
        n = self.node
        total_nodes = config.total_nodes
        return (
            f"Swarm size: {total_nodes} nodes.\n"
            f"My capital: {n.capital:.2f} | DQ: {n.survival.dq:.3f} | Liveness: {n.survival.liveness:.3f}\n"
            f"My niche: {n.node_niche()} | Dominant niche: {max(n.population_niche_counts(), key=n.population_niche_counts().get)}\n"
            f"Population diversity: {n.population_diversity():.2f} | CRDT size: {len(n.crdt.state)}\n"
            f"Last known fitness: {n.engine.champion[1] if n.engine.champion else 0.0:.4f}"
        )

    def _get_market_context(self) -> str:
        """Рыночный контекст из последнего снимка."""
        m = getattr(self.node, '_last_market', None)
        if m:
            price = m.get('price', 'N/A')
            return f"Current price: {price}\nVolatility: {self.node._current_volatility():.4f}"
        return "Market data unavailable"
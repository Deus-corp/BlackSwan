"""
Telemetry – единый слой наблюдаемости (логи, события, метрики, Telegram).
"""
import logging
from typing import Dict, Any
from src.core.events import Event
from swarm_config import config
from mvp.lab_swarm_demo.mutation_metrics import get_llm_stats, update_llm_impact

logger = logging.getLogger(__name__)


class Telemetry:
    def __init__(self, node_id: str, event_store, telegram_notifier,
                 get_llm_stats_func, update_llm_impact_func):
        self.node_id = node_id
        self.event_store = event_store
        self.telegram = telegram_notifier
        self._get_llm_stats = get_llm_stats_func
        self._update_llm_impact = update_llm_impact_func

    async def trade(self, step: int, symbol: str, side: str, amount: float,
                    tx_hash: str, status: str, capital_before: float,
                    capital_after: float, trace_id: str):
        """Запись события сделки и уведомление."""
        self.event_store.append(Event.create(
            node_id=self.node_id,
            event_type="trade_executed",
            payload={
                "step": step,
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "tx_hash": tx_hash,
                "status": status,
                "capital_before": capital_before,
                "capital_after": capital_after,
                "trace_id": trace_id,
            },
            parent_id=trace_id,
        ))
        await self.telegram.send(
            f"🦢 <b>Trade</b>\n"
            f"Node: {self.node_id}\n"
            f"Step: {step}\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Amount: {amount}\n"
            f"Status: {status}\n"
            f"Capital: {capital_after:.2f}"
        )

    def heartbeat(self, step: int, capital: float, dq: float,
                  fitness: float, diversity: float, crdt_size: int,
                  llm_mutations: int, niche_counts: dict, trace_id: str):
        """Периодическая запись heartbeat."""
        stats = {
            "step": step,
            "capital": round(capital, 4),
            "dq": round(dq, 4),
            "fitness": round(fitness, 4),
            "diversity": round(diversity, 4),
            "crdt_size": crdt_size,
            "llm_mutations": llm_mutations,
            "niche_counts": niche_counts,
        }
        logger.info(f"STATS | {stats}")
        self.event_store.append(Event.create(
            node_id=self.node_id,
            event_type="heartbeat",
            payload=stats,
            parent_id=trace_id,
        ))

    def mutation_event(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str):
        """Запись события мутации (уже частично делается в mutation_engine, но здесь для полноты)."""
        self.event_store.append(Event.create(
            node_id=self.node_id,
            event_type="llm_mutation",
            payload={
                "old_params": old_params,
                "new_params": new_params,
                "context": context,
            },
            parent_id=None,
        ))

    def update_impact(self, current_capital: float):
        self._update_llm_impact(current_capital)

    def get_llm_stats(self):
        return self._get_llm_stats()

    async def low_capital_alert(self, capital: float, threshold: float):
        await self.telegram.send(
            f"⚠️ <b>Low capital alert</b>\n"
            f"Node: {self.node_id}\n"
            f"Capital: {capital:.2f} (threshold: {threshold})"
        )

    async def spore_failure(self, step: int, capital: float, dq: float,
                            fitness: float, diversity: float, crdt_size: int,
                            trace_id: str):
        """Событие перед гибелью узла."""
        self.event_store.append(Event.create(
            node_id=self.node_id,
            event_type="spore_failure",
            payload={
                "step": step,
                "capital": capital,
                "dq": dq,
                "fitness": fitness,
                "diversity": diversity,
                "crdt_size": crdt_size,
                "trace_id": trace_id,
            },
            parent_id=trace_id,
        ))
        logger.info(f"[{self.node_id}] spore failure recorded")
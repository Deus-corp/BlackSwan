"""
Telemetry – единый слой наблюдаемости (логи, события, метрики, Telegram).
"""
import logging
from typing import Dict, Any, Callable
from src.core.events import Event
from swarm_config import config
from mvp.lab_swarm_demo.mutation_metrics import get_llm_stats, update_llm_impact

logger = logging.getLogger(__name__)


class Telemetry:
    """
    Unified observability layer for logging, events, metrics, and Telegram notifications.
    Manages recording various events and sending alerts related to node activities.
    """
    def __init__(self, node_id: str, event_store: Any, telegram_notifier: Any,
                 get_llm_stats_func: Callable[[], Dict[str, Any]],
                 update_llm_impact_func: Callable[[float], None]) -> None:
        """
        Initializes the Telemetry instance.

        Args:
            node_id: The unique identifier for the node.
            event_store: An object with an `append` method to store events (e.g., a list or custom EventStore).
            telegram_notifier: An object with a `send` method for Telegram notifications.
            get_llm_stats_func: A callable function to retrieve LLM statistics. Expected to return a dict.
            update_llm_impact_func: A callable function to update LLM impact based on current capital.
        """
        self.node_id = node_id
        self.event_store = event_store
        self.telegram = telegram_notifier
        self._get_llm_stats = get_llm_stats_func
        self._update_llm_impact = update_llm_impact_func

    async def trade(self, step: int, symbol: str, side: str, amount: float,
                    tx_hash: str, status: str, capital_before: float,
                    capital_after: float, trace_id: str) -> None:
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
                  llm_mutations: int, niche_counts: Dict[str, int], trace_id: str) -> None:
        """Периодическая запись heartbeat."""
        stats: Dict[str, Any] = { # Added type hint for stats dictionary
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

    def mutation_event(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str) -> None:
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

    def update_impact(self, current_capital: float) -> None: # Added type hint for return
        self._update_llm_impact(current_capital)

    def get_llm_stats(self) -> Dict[str, Any]: # Assuming Dict[str, Any] as return type
        return self._get_llm_stats()

    async def low_capital_alert(self, capital: float, threshold: float) -> None: # Added type hint for return
        await self.telegram.send(
            f"⚠️ <b>Low capital alert</b>\n"
            f"Node: {self.node_id}\n"
            f"Capital: {capital:.2f} (threshold: {threshold})"
        )

    async def spore_failure(self, step: int, capital: float, dq: float,
                            fitness: float, diversity: float, crdt_size: int,
                            trace_id: str) -> None:
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
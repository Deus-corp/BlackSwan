"""
Telemetry – A unified observability layer for tracking node operations, events, and metrics.

This module provides an abstraction over event logging, metrics aggregation, 
and alert notifications for the node ecosystem.
"""
import logging
from typing import Dict, Any, Callable, Protocol, Final
from src.core.events import Event

logger: Final = logging.getLogger(__name__)

class EventStoreLike(Protocol):
    """Protocol for a repository that persists system events."""
    def append(self, event: Event) -> None:
        ...

class TelegramNotifierLike(Protocol):
    """Protocol for a service capable of sending Telegram alerts."""
    async def send(self, message: str) -> None:
        ...

class Telemetry:
    """
    Centralized observability manager for node activity tracking, LLM health checks,
    and incident alerting.
    """

    def __init__(
        self, 
        node_id: str, 
        event_store: EventStoreLike, 
        telegram_notifier: TelegramNotifierLike,
        get_llm_stats_func: Callable[[], Dict[str, Any]],
        update_llm_impact_func: Callable[[float], None]
    ) -> None:
        self.node_id = node_id
        self.event_store = event_store
        self.telegram = telegram_notifier
        self._get_llm_stats = get_llm_stats_func
        self._update_llm_impact = update_llm_impact_func

    async def trade(
        self, 
        step: int, 
        symbol: str, 
        side: str, 
        amount: float,
        tx_hash: str, 
        status: str, 
        capital_before: float,
        capital_after: float, 
        trace_id: str
    ) -> None:
        """Logs a trade execution event and pushes a notification to Telegram."""
        event = Event.create(
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
        )
        self.event_store.append(event)
        
        msg = (
            f"🦢 <b>Trade</b>\n"
            f"Node: {self.node_id}\n"
            f"Step: {step}\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Amount: {amount}\n"
            f"Status: {status}\n"
            f"Capital: {capital_after:.2f}"
        )
        await self.telegram.send(msg)

    def heartbeat(
        self, 
        step: int, 
        capital: float, 
        dq: float,
        fitness: float, 
        diversity: float, 
        crdt_size: int,
        llm_mutations: int, 
        niche_counts: Dict[str, int], 
        trace_id: str
    ) -> None:
        """Records system health statistics and emits a heartbeat event."""
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
        logger.info(f"Heartbeat | Node: {self.node_id} | Stats: {stats}")
        
        event = Event.create(
            node_id=self.node_id,
            event_type="heartbeat",
            payload=stats,
            parent_id=trace_id,
        )
        self.event_store.append(event)

    def mutation_event(self, old_params: Dict[str, float], new_params: Dict[str, float], context: str) -> None:
        """Logs changes to model parameters caused by LLM-driven evolution."""
        event = Event.create(
            node_id=self.node_id,
            event_type="llm_mutation",
            payload={
                "old_params": old_params,
                "new_params": new_params,
                "context": context,
            },
            parent_id=None,
        )
        self.event_store.append(event)

    def update_impact(self, current_capital: float) -> None:
        """Updates internal LLM impact metrics based on performance."""
        self._update_llm_impact(current_capital)

    def get_llm_stats(self) -> Dict[str, Any]:
        """Retrieves current statistics for the LLM component."""
        return self._get_llm_stats()

    async def low_capital_alert(self, capital: float, threshold: float) -> None:
        """Sends an urgent Telegram notification if capital drops below the defined threshold."""
        await self.telegram.send(
            f"⚠️ <b>Low capital alert</b>\n"
            f"Node: {self.node_id}\n"
            f"Capital: {capital:.2f} (threshold: {threshold})"
        )

    async def spore_failure(
        self, 
        step: int, 
        capital: float, 
        dq: float,
        fitness: float, 
        diversity: float, 
        crdt_size: int,
        trace_id: str
    ) -> None:
        """Logs the termination of a node and emits a spore failure event."""
        payload = {
            "step": step,
            "capital": capital,
            "dq": dq,
            "fitness": fitness,
            "diversity": diversity,
            "crdt_size": crdt_size,
            "trace_id": trace_id,
        }
        event = Event.create(
            node_id=self.node_id,
            event_type="spore_failure",
            payload=payload,
            parent_id=trace_id,
        )
        self.event_store.append(event)
        logger.warning(f"[{self.node_id}] Spore failure at step {step}")
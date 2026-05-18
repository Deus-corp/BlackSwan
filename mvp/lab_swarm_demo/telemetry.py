"""
Telemetry – a unified observability layer (logs, events, metrics, Telegram).
"""
import logging
from typing import Dict, Any, Callable, Optional
from src.core.events import Event
# from swarm_config import config # Unused import, can be removed if not needed elsewhere
# Mypy might complain about relative imports if src is not properly configured in path.
# Assuming 'src' is importable.
# from mvp.lab_swarm_demo.mutation_metrics import get_llm_stats, update_llm_impact # These are passed as callables now

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
        self.node_id: str = node_id
        self.event_store: Any = event_store
        self.telegram: Any = telegram_notifier
        self._get_llm_stats: Callable[[], Dict[str, Any]] = get_llm_stats_func
        self._update_llm_impact: Callable[[float], None] = update_llm_impact_func

    async def trade(self, step: int, symbol: str, side: str, amount: float,
                    tx_hash: str, status: str, capital_before: float,
                    capital_after: float, trace_id: str) -> None:
        """
        Records a trade event and sends a Telegram notification.

        Args:
            step: The current simulation step.
            symbol: The trading symbol (e.g., "BTC/USDT").
            side: The trade side ("buy" or "sell").
            amount: The amount traded.
            tx_hash: The transaction hash.
            status: The status of the trade (e.g., "filled", "pending").
            capital_before: The node's capital before the trade.
            capital_after: The node's capital after the trade.
            trace_id: A unique identifier for the transaction/action chain.
        """
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
        """
        Records a periodic heartbeat event containing key node statistics.

        Args:
            step: The current simulation step.
            capital: The current capital of the node.
            dq: The Detection Quotient (survival metric).
            fitness: The fitness of the node's best genome.
            diversity: The diversity of the node's genome population.
            crdt_size: The current size of the CRDT state.
            llm_mutations: The total number of LLM-driven mutations.
            niche_counts: A dictionary showing the count of genomes per niche.
            trace_id: A unique identifier for the action chain.
        """
        stats: Dict[str, Any] = {
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
        """
        Records an LLM mutation event.

        Args:
            old_params: The parameters before the mutation.
            new_params: The parameters after the mutation.
            context: The context or reason for the mutation.
        """
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

    def update_impact(self, current_capital: float) -> None:
        """
        Updates the LLM impact metric based on the node's current capital.

        Args:
            current_capital: The current capital of the node.
        """
        self._update_llm_impact(current_capital)

    def get_llm_stats(self) -> Dict[str, Any]:
        """
        Retrieves current LLM statistics.

        Returns:
            A dictionary containing LLM-related statistics.
        """
        return self._get_llm_stats()

    async def low_capital_alert(self, capital: float, threshold: float) -> None:
        """
        Sends a Telegram alert if the node's capital falls below a specified threshold.

        Args:
            capital: The current capital of the node.
            threshold: The capital threshold below which an alert is triggered.
        """
        await self.telegram.send(
            f"⚠️ <b>Low capital alert</b>\n"
            f"Node: {self.node_id}\n"
            f"Capital: {capital:.2f} (threshold: {threshold})"
        )

    async def spore_failure(self, step: int, capital: float, dq: float,
                            fitness: float, diversity: float, crdt_size: int,
                            trace_id: str) -> None:
        """
        Records an event indicating the impending failure (death) of a node.

        Args:
            step: The current simulation step.
            capital: The capital of the node at the time of failure.
            dq: The Detection Quotient at the time of failure.
            fitness: The fitness of the node's best genome at the time of failure.
            diversity: The diversity of the node's genome population at the time of failure.
            crdt_size: The current size of the CRDT state.
            trace_id: A unique identifier for the action chain.
        """
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
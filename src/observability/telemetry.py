"""Unified observability layer for node events, metrics, and alerts."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Protocol

from src.core.events import Event

logger = logging.getLogger(__name__)


class EventStoreLike(Protocol):
    """Repository that persists system events."""

    def append(self, event: Event) -> None:
        ...


class TelegramNotifierLike(Protocol):
    """Service capable of sending Telegram alerts."""

    async def send(self, message: str) -> bool:
        ...


class Telemetry:
    """Centralized observability manager for node activity and incident alerting."""

    def __init__(
        self,
        node_id: str,
        event_store: EventStoreLike,
        telegram_notifier: TelegramNotifierLike,
        get_llm_stats_func: Callable[[], dict[str, Any]] | None = None,
        update_llm_impact_func: Callable[[float], None] | None = None,
    ) -> None:
        clean_node_id = str(node_id or "").strip()
        if not clean_node_id:
            raise ValueError("node_id cannot be empty")

        self.node_id = clean_node_id
        self.event_store = event_store
        self.telegram = telegram_notifier
        self._get_llm_stats = get_llm_stats_func or (lambda: {})
        self._update_llm_impact = update_llm_impact_func or (lambda _capital: None)

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
        trace_id: str,
    ) -> None:
        """Record a trade execution event and send a Telegram notification."""
        payload = {
            "step": int(step),
            "symbol": str(symbol or ""),
            "side": str(side or "").lower(),
            "amount": float(amount),
            "tx_hash": str(tx_hash or ""),
            "status": str(status or ""),
            "capital_before": float(capital_before),
            "capital_after": float(capital_after),
            "capital_delta": float(capital_after) - float(capital_before),
            "trace_id": str(trace_id or ""),
        }

        self._append_event("trade_executed", payload, parent_id=payload["trace_id"] or None)

        message = (
            "🦢 <b>Trade</b>\n"
            f"Node: {self.node_id}\n"
            f"Step: {payload['step']}\n"
            f"Symbol: {payload['symbol']}\n"
            f"Side: {payload['side']}\n"
            f"Amount: {payload['amount']}\n"
            f"Status: {payload['status']}\n"
            f"Capital: {payload['capital_after']:.2f}"
        )
        await self._send_alert(message)

    def heartbeat(
        self,
        step: int,
        capital: float,
        dq: float,
        fitness: float,
        diversity: float,
        crdt_size: int,
        llm_mutations: int,
        niche_counts: dict[str, int],
        trace_id: str,
    ) -> None:
        """Record node heartbeat metrics."""
        stats = {
            "step": int(step),
            "capital": round(float(capital), 4),
            "dq": round(float(dq), 4),
            "fitness": round(float(fitness), 4),
            "diversity": round(float(diversity), 4),
            "crdt_size": int(crdt_size),
            "llm_mutations": int(llm_mutations),
            "niche_counts": dict(niche_counts or {}),
            "trace_id": str(trace_id or ""),
        }

        logger.info("Heartbeat | node=%s stats=%s", self.node_id, stats)
        self._append_event("heartbeat", stats, parent_id=stats["trace_id"] or None)

    def mutation_event(
        self,
        old_params: dict[str, float],
        new_params: dict[str, float],
        context: str,
    ) -> None:
        """Record LLM-driven strategy parameter mutation."""
        payload = {
            "old_params": dict(old_params or {}),
            "new_params": dict(new_params or {}),
            "context": str(context or ""),
        }
        self._append_event("llm_mutation", payload)

    def update_impact(self, current_capital: float) -> None:
        """Update internal LLM impact metrics based on performance."""
        try:
            self._update_llm_impact(float(current_capital))
        except Exception:
            logger.exception("[%s] Failed to update LLM impact.", self.node_id)

    def get_llm_stats(self) -> dict[str, Any]:
        """Return current LLM component statistics."""
        try:
            stats = self._get_llm_stats()
            return dict(stats) if isinstance(stats, dict) else {"value": stats}
        except Exception:
            logger.exception("[%s] Failed to get LLM stats.", self.node_id)
            return {}

    async def low_capital_alert(self, capital: float, threshold: float) -> None:
        """Send low-capital alert and persist an alert event."""
        payload = {
            "capital": float(capital),
            "threshold": float(threshold),
            "severity": "warning",
        }
        self._append_event("low_capital_alert", payload)

        await self._send_alert(
            "⚠️ <b>Low capital alert</b>\n"
            f"Node: {self.node_id}\n"
            f"Capital: {payload['capital']:.2f} "
            f"(threshold: {payload['threshold']:.2f})"
        )

    async def spore_failure(
        self,
        step: int,
        capital: float,
        dq: float,
        fitness: float,
        diversity: float,
        crdt_size: int,
        trace_id: str,
    ) -> None:
        """Record node termination/failure event and send alert."""
        payload = {
            "step": int(step),
            "capital": float(capital),
            "dq": float(dq),
            "fitness": float(fitness),
            "diversity": float(diversity),
            "crdt_size": int(crdt_size),
            "trace_id": str(trace_id or ""),
        }

        self._append_event("spore_failure", payload, parent_id=payload["trace_id"] or None)
        logger.warning("[%s] Spore failure at step %s", self.node_id, payload["step"])

        await self._send_alert(
            "🧬 <b>Spore failure</b>\n"
            f"Node: {self.node_id}\n"
            f"Step: {payload['step']}\n"
            f"Capital: {payload['capital']:.2f}\n"
            f"Fitness: {payload['fitness']:.4f}"
        )

    def _append_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        parent_id: str | None = None,
    ) -> Event | None:
        try:
            event = Event.create(
                node_id=self.node_id,
                event_type=event_type,
                payload=payload,
                parent_id=parent_id,
            )
            self.event_store.append(event)
            return event
        except Exception:
            logger.exception("[%s] Failed to append telemetry event type=%s.", self.node_id, event_type)
            return None

    async def _send_alert(self, message: str) -> bool:
        send = getattr(self.telegram, "send", None)
        if not callable(send):
            logger.debug("[%s] Telegram notifier has no send() method.", self.node_id)
            return False

        try:
            result = send(message)
            if inspect.isawaitable(result):
                result = await result
            return bool(result) if result is not None else True
        except Exception:
            logger.exception("[%s] Failed to send Telegram telemetry alert.", self.node_id)
            return False
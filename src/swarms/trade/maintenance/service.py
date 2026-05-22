"""Periodic maintenance for the trade swarm node."""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from src.swarms.trade.context import RuntimeContext
from src.core.events import Event

logger = logging.getLogger("SwarmNode.Maintenance")

class MaintenanceService:
    """
    Handles periodic housekeeping for trade nodes:
    - Capital watchdog for risk mitigation
    - Memory lifecycle and deduplication
    - Semantic rule derivation
    - CRDT state pruning
    - Reputation updates
    """

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    async def run(self, current_params: Dict[str, float]) -> None:
        """Executes periodic maintenance tasks based on step counts."""
        self._apply_capital_watchdog(current_params)

        if self._ctx.step_count % 500 == 0:
            await self._memory_snapshot()

        if self._ctx.step_count % 200 == 0:
            await self._deep_maintenance()

    def _apply_capital_watchdog(self, current_params: Dict[str, float]) -> None:
        """Monitors capital levels and reverts parameters towards safe defaults if low."""
        if self._ctx.capital >= float(self._ctx.config.capital_watchdog_threshold):
            return

        logger.warning(
            "[%s] Watchdog: low capital (%.2f), gradual rollback of parameters",
            self._ctx.config.node_id,
            self._ctx.capital,
        )

        std_params = {
            "max_risk_per_trade": 0.05,
            "phi_llm": 0.15,
            "stop_loss_ratio": 0.02,
            "trailing_stop_ratio": 0.01,
            "momentum_window": 10.0,
            "volatility_threshold": 0.02,
        }

        for key, std_value in std_params.items():
            current_val = float(current_params.get(key, std_value))
            current_params[key] = (current_val * 0.8) + (std_value * 0.2)

        if hasattr(self._ctx.capital_manager, "apply_dq_delta"):
            try:
                self._ctx.capital_manager.apply_dq_delta(-0.05)
            except Exception:
                logger.debug("Failed to apply capital_manager.apply_dq_delta", exc_info=True)

    async def _memory_snapshot(self) -> None:
        """Performs memory cleanup, deduplication, and persistence."""
        memory = getattr(self._ctx, "memory", None)
        if memory is None:
            return

        try:
            self._deduplicate_memory()

            if len(memory.records) > memory.max_size:
                memory.records = memory.records[-memory.max_size:]

            memory_api = getattr(self._ctx, "memory_api", None)
            if getattr(self._ctx, "memory_api_enabled", False) and memory_api:
                await memory_api.save_to_db()

                event_store = getattr(self._ctx, "event_store", None)
                if event_store:
                    event_store.append(
                        Event.create(
                            node_id=self._ctx.config.node_id,
                            event_type="memory_snapshot_created",
                            payload={
                                "step": self._ctx.step_count,
                                "records_count": len(getattr(memory_api, "_records", [])),
                                "trace_id": self._ctx.trace_id,
                            },
                            parent_id=self._ctx.trace_id,
                        )
                    )
        except Exception as e:
            logger.warning("Memory snapshot failed: %s", e, exc_info=True)

    async def _deep_maintenance(self) -> None:
        """Performs expensive maintenance tasks like compression and reputation analysis."""
        try:
            self._derive_semantic_rules()
            await self._prune_crdt()
            await self._update_reputation_from_top_genomes()

            memory_api = getattr(self._ctx, "memory_api", None)
            if getattr(self._ctx, "memory_api_enabled", False) and hasattr(memory_api, "compress"):
                stats = await memory_api.compress()
                logger.info("Memory compression stats: %s", stats)
        except Exception as e:
            logger.warning("Deep maintenance failed: %s", e, exc_info=True)

    def _deduplicate_memory(self) -> None:
        """Removes duplicate memory records based on parameters."""
        memory = getattr(self._ctx, "memory", None)
        if not memory or not hasattr(memory, "records"):
            return

        deduplicated: Dict[frozenset[Tuple[str, Any]], Any] = {}
        for rec in memory.records:
            if isinstance(rec, dict) and isinstance(rec.get("params"), dict):
                params = rec["params"]
                key = frozenset(params.items())
                deduplicated[key] = rec

        memory.records = list(deduplicated.values())

    def _derive_semantic_rules(self) -> None:
        semantic = getattr(self._ctx, "semantic", None)
        memory = getattr(self._ctx, "memory", None)
        if semantic and memory and hasattr(semantic, "derive_rules") and hasattr(memory, "to_dict_list"):
            semantic.derive_rules(memory.to_dict_list())

    async def _prune_crdt(self) -> None:
        crdt = getattr(self._ctx, "crdt", None)
        if not crdt:
            return
        try:
            if hasattr(crdt, "prune"): await crdt.prune()
            if hasattr(crdt, "prune_heartbeats"): await crdt.prune_heartbeats(max_age_seconds=600)
        except Exception:
            logger.debug("CRDT pruning failed", exc_info=True)

    async def _update_reputation_from_top_genomes(self) -> None:
        """Updates local node reputation based on top-performing genome data."""
        crdt = getattr(self._ctx, "crdt", None)
        reputation = getattr(self._ctx, "reputation", None)
        engine = getattr(self._ctx, "engine", None)
        crypto = getattr(self._ctx, "crypto", None)

        if not (crdt and reputation and engine and crypto):
            return

        try:
            top_genomes = await crdt.get_top(20)
            if not top_genomes:
                return

            sample = random.choice(top_genomes)
            pubkey_hex = sample.get("origin_pubkey_hex")
            if not pubkey_hex or pubkey_hex == getattr(crypto, "public_bytes_hex", ""):
                return

            sample_params = {
                k: float(v) for k, v in sample.get("params", {}).items() if isinstance(v, (int, float))
            }

            actual_fit = engine._fitness(sample_params) if hasattr(engine, "_fitness") else 0.0
            claimed_fit = float(sample.get("fitness", 0.0))

            if hasattr(reputation, "update"):
                reputation.update(bytes.fromhex(pubkey_hex), claimed_fit, actual_fit)
        except Exception as e:
            logger.warning("Reputation update skipped: %s", e, exc_info=True)
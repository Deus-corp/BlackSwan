"""Periodic maintenance for the trade swarm node."""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, Optional, Tuple

from ..context import RuntimeContext

logger = logging.getLogger("SwarmNode.Maintenance")


class MaintenanceService:
    """
    Handles periodic housekeeping:
    - capital watchdog
    - memory deduplication
    - memory persistence / compression
    - semantic derivation
    - CRDT pruning
    - reputation updates from imported genomes
    """

    def __init__(self, ctx: RuntimeContext) -> None:
        self._ctx = ctx

    async def run(self, current_params: Dict[str, float]) -> None:
        self._apply_capital_watchdog(current_params)

        if self._ctx.step_count % 500 == 0:
            await self._memory_snapshot()

        if self._ctx.step_count % 200 == 0:
            await self._deep_maintenance()

    def _apply_capital_watchdog(self, current_params: Dict[str, float]) -> None:
        if self._ctx.capital >= float(self._ctx.config.capital_watchdog_threshold):
            return

        logger.warning(
            "[%s] Watchdog: low capital (%.2f), gradual rollback of parameters",
            self._ctx.config.node_id,
            self._ctx.capital,
        )

        std_params: Dict[str, float] = {
            "max_risk_per_trade": 0.05,
            "phi_llm": 0.15,
            "stop_loss_ratio": 0.02,
            "trailing_stop_ratio": 0.01,
            "momentum_window": 10.0,
            "volatility_threshold": 0.02,
        }

        for key, std_value in std_params.items():
            current_value = float(current_params.get(key, std_value))
            current_params[key] = current_value * 0.8 + std_value * 0.2

        if hasattr(self._ctx.capital_manager, "apply_dq_delta"):
            try:
                self._ctx.capital_manager.apply_dq_delta(-0.05)
            except Exception:
                logger.debug("capital_manager.apply_dq_delta failed", exc_info=True)

    async def _memory_snapshot(self) -> None:
        memory = getattr(self._ctx, "memory", None)
        if memory is None:
            return

        try:
            self._deduplicate_memory()

            if len(memory.records) > memory.max_size:
                memory.records = memory.records[-memory.max_size:]

            memory_api = getattr(self._ctx, "memory_api", None)
            memory_api_enabled = bool(getattr(self._ctx, "memory_api_enabled", False))

            if memory_api_enabled and memory_api is not None:
                await memory_api.save_to_db()

                event_store = getattr(self._ctx, "event_store", None)
                if event_store is not None:
                    try:
                        from src.core.events import Event

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
                    except Exception:
                        logger.debug("memory snapshot event append failed", exc_info=True)

        except Exception as e:
            logger.warning("Memory snapshot failed: %s", e, exc_info=True)

    async def _deep_maintenance(self) -> None:
        try:
            self._derive_semantic_rules()
            await self._prune_crdt()
            await self._update_reputation_from_top_genomes()

            memory_api = getattr(self._ctx, "memory_api", None)
            memory_api_enabled = bool(getattr(self._ctx, "memory_api_enabled", False))
            if memory_api_enabled and memory_api is not None and hasattr(memory_api, "compress"):
                stats = await memory_api.compress()
                logger.info("Memory compression stats: %s", stats)

        except Exception as e:
            logger.warning("Deep maintenance failed: %s", e, exc_info=True)

    def _deduplicate_memory(self) -> None:
        memory = getattr(self._ctx, "memory", None)
        if memory is None or not hasattr(memory, "records"):
            return

        deduplicated_records: Dict[frozenset[Tuple[str, Any]], Any] = {}

        for rec in getattr(memory, "records", []):
            if not isinstance(rec, dict):
                continue
            params = rec.get("params")
            if not isinstance(params, dict):
                continue
            key = frozenset(params.items())
            deduplicated_records[key] = rec

        memory.records = list(deduplicated_records.values())

    def _derive_semantic_rules(self) -> None:
        semantic = getattr(self._ctx, "semantic", None)
        memory = getattr(self._ctx, "memory", None)
        if semantic is None or memory is None:
            return

        if hasattr(semantic, "derive_rules") and hasattr(memory, "to_dict_list"):
            semantic.derive_rules(memory.to_dict_list())

    async def _prune_crdt(self) -> None:
        crdt = getattr(self._ctx, "crdt", None)
        if crdt is None:
            return

        try:
            if hasattr(crdt, "prune"):
                await crdt.prune()
            if hasattr(crdt, "prune_heartbeats"):
                await crdt.prune_heartbeats(max_age_seconds=600)
        except Exception:
            logger.debug("CRDT prune failed", exc_info=True)

    async def _update_reputation_from_top_genomes(self) -> None:
        crdt = getattr(self._ctx, "crdt", None)
        reputation = getattr(self._ctx, "reputation", None)
        engine = getattr(self._ctx, "engine", None)
        crypto = getattr(self._ctx, "crypto", None)

        if crdt is None or reputation is None or engine is None or crypto is None:
            return

        try:
            top_genomes = await crdt.get_top(20)
            if not top_genomes:
                return

            sample: Dict[str, Any] = random.choice(top_genomes)
            pubkey_hex: Optional[str] = sample.get("origin_pubkey_hex")
            if not pubkey_hex or pubkey_hex == getattr(crypto, "public_bytes_hex", ""):
                return

            sample_params: Dict[str, float] = {
                k: float(v)
                for k, v in sample.get("params", {}).items()
                if isinstance(v, (int, float))
            }

            actual_fit: float = 0.0
            if hasattr(engine, "_fitness"):
                actual_fit = float(engine._fitness(sample_params))

            claimed_fit: float = float(sample.get("fitness", 0.0))
            pubkey_bytes: bytes = bytes.fromhex(pubkey_hex)

            if hasattr(reputation, "update"):
                reputation.update(pubkey_bytes, claimed_fit, actual_fit)

        except Exception as e:
            logger.warning("Reputation update skipped: %s", e, exc_info=True)
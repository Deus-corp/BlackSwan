"""Evolution Engine – orchestrates mutation, genetic evolution, and memory replay."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from typing import Any, Callable, Optional, Protocol

from swarm_config import config
from src.economy.roi_dispatcher import ROIDispatcher
from src.security.gossip_envelope import sign_envelope
from src.trading.mutation_metrics import note_llm_mutation

logger = logging.getLogger(__name__)


class GenomeProtocol(Protocol):
    params: dict[str, Any]
    fitness: float
    niche: str


class MutationEngineProtocol(Protocol):
    def mutate(self, base_params: dict[str, Any], context: str) -> dict[str, Any]:
        ...


class SwarmNodeProtocol(Protocol):
    node_id: str
    step_count: int
    llm: Any
    mutation_engine: MutationEngineProtocol
    _prev_price: float
    _prev_prev_price: float
    _last_market: Optional[dict[str, Any]]
    internet_researcher: Any
    tradingview_enabled: bool
    tradingview_webhook: Any
    orderbook_enabled: bool
    orderbook_analyzers: dict[str, Any]
    _current_volatility: Callable[[], float]
    survival: Any
    capital: float
    node_niche: Callable[[], str]
    memory: Any
    engine: Any
    dict_to_genome: Callable[[dict[str, Any]], GenomeProtocol]
    make_genome: Callable[[dict[str, Any], float], dict[str, Any]]
    current_params: dict[str, Any]
    dispatcher: ROIDispatcher
    crdt: Any
    crypto: Any
    gossip_seq_no: int
    gossip_lamport_ts: int
    gossip_public_bytes: bytes | str
    gossip_key_id: str
    gossip_private_key: bytes | str


class EvolutionEngine:
    """Manage LLM-driven mutation, genetic evolution, and strategy memory."""

    MUTATION_INTERVAL_STEPS = 100
    GENETIC_INTERVAL_STEPS = 50
    GOSSIP_DOMAIN = "blackswan-gossip-v1"
    GOSSIP_TTL_MS = 60_000

    def __init__(self, node: SwarmNodeProtocol) -> None:
        self.node = node
        self.llm = getattr(node, "llm", None)
        self.mutation_engine = getattr(node, "mutation_engine", None)

        if self.mutation_engine is None:
            raise ValueError("node.mutation_engine is required")

        self._ensure_node_market_attrs()
        logger.debug("EvolutionEngine initialized for node %s.", self.node.node_id)

    async def tick(self, market: dict[str, Any]) -> None:
        """Execute one periodic evolution tick."""
        if not isinstance(market, dict):
            logger.warning("Evolution tick ignored non-dict market payload: %r", type(market))
            return

        step = int(getattr(self.node, "step_count", 0))
        node_id = str(getattr(self.node, "node_id", "unknown"))

        self._update_market_state(market)

        if step > 0 and step % self.MUTATION_INTERVAL_STEPS == 0:
            logger.debug("Node %s performing LLM mutation at step %s.", node_id, step)
            await self._safe_mutate_with_context()

        if step > 0 and step % self.GENETIC_INTERVAL_STEPS == 0:
            logger.debug("Node %s performing genetic step at step %s.", node_id, step)
            await self._safe_genetic_step()

    async def _safe_mutate_with_context(self) -> None:
        try:
            await self._mutate_with_context()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("LLM mutation failed for node %s: %s", self.node.node_id, exc)

    async def _safe_genetic_step(self) -> None:
        try:
            await self._genetic_step()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Genetic step failed for node %s: %s", self.node.node_id, exc)

    async def _mutate_with_context(self) -> None:
        """Gather context, mutate champion/current params, and add new genome to population."""
        node_id = str(getattr(self.node, "node_id", "unknown"))
        logger.info("Node %s gathering context for LLM mutation.", node_id)

        context = await self._build_mutation_context()
        base_params = self._get_base_params()
        if not base_params:
            logger.warning("Node %s has no base params for mutation; skipping.", node_id)
            return

        logger.info("Node %s calling mutation engine with context length=%s.", node_id, len(context))

        maybe_new_params = self.mutation_engine.mutate(dict(base_params), context)
        if inspect.isawaitable(maybe_new_params):
            maybe_new_params = await maybe_new_params

        if not isinstance(maybe_new_params, dict):
            logger.warning("Node %s mutation engine returned non-dict params: %r", node_id, type(maybe_new_params))
            return

        new_params = dict(maybe_new_params)
        if new_params == base_params:
            logger.info("Node %s mutation produced no parameter change.", node_id)
            return

        genome = self._params_to_genome(new_params)
        if genome is None:
            logger.warning("Node %s could not convert mutated params to genome.", node_id)
            return

        genetic_engine = getattr(self.node, "engine", None)
        add_genome = getattr(genetic_engine, "add_genome", None)
        if not callable(add_genome):
            logger.warning("Node %s genetic engine lacks add_genome(); mutated genome not added.", node_id)
            return

        add_genome(genome)
        note_llm_mutation()
        logger.info("Node %s added LLM-mutated genome to population.", node_id)

    async def _genetic_step(self) -> None:
        """Evolve population, publish champion, update current params, and store memory."""
        node_id = str(getattr(self.node, "node_id", "unknown"))
        genetic_engine = getattr(self.node, "engine", None)

        evolve_generation = getattr(genetic_engine, "evolve_generation", None)
        if not callable(evolve_generation):
            logger.warning("Node %s genetic engine lacks evolve_generation(); skipping.", node_id)
            return

        evolve_generation()

        champion = getattr(genetic_engine, "champion", None)
        if not self._valid_champion(champion):
            logger.debug("Node %s has no positive-fitness champion; skipping publish/update.", node_id)
            return

        champion_params, champion_fitness = champion
        champion_params = dict(champion_params)
        champion_fitness = float(champion_fitness)

        volatility = self._current_volatility()
        dq = self._current_dq()

        params_to_publish = self._apply_semantic_rules(champion_params, volatility, dq)
        genome_dict = self._make_genome_dict(params_to_publish, champion_fitness)
        if genome_dict is None:
            logger.warning("Node %s could not build genome dict from champion.", node_id)
            return

        await self._publish_genome(genome_dict)

        if self._is_champion_better(champion_params, champion_fitness):
            self.node.current_params = champion_params
            self.node.dispatcher = ROIDispatcher(config=champion_params)
            logger.info(
                "Node %s updated current params to champion fitness=%.4f.",
                node_id,
                champion_fitness,
            )

        self._add_champion_to_memory(
            params=champion_params,
            fitness=champion_fitness,
            volatility=volatility,
            dq=dq,
        )

    async def _build_mutation_context(self) -> str:
        parts: list[str] = []

        await self._append_research_context(parts)
        self._append_tradingview_context(parts)
        await self._append_orderbook_context(parts)
        self._append_market_context(parts)
        self._append_node_context(parts)
        self._append_memory_context(parts)
        self._append_population_context(parts)

        context = "\n".join(part for part in parts if part)
        if not context:
            logger.warning("Node %s generated empty context for LLM mutation.", self.node.node_id)

        return context

    async def _append_research_context(self, parts: list[str]) -> None:
        if not bool(getattr(config, "internet_researcher_enabled", False)):
            return

        researcher = getattr(self.node, "internet_researcher", None)
        gather_context = getattr(researcher, "gather_context", None)
        if not callable(gather_context):
            return

        try:
            result = gather_context()
            if inspect.isawaitable(result):
                result = await result
            if result:
                parts.append(str(result))
        except Exception as exc:
            logger.warning("Internet researcher context failed for %s: %s", self.node.node_id, exc)

    def _append_tradingview_context(self, parts: list[str]) -> None:
        if not bool(getattr(self.node, "tradingview_enabled", False)):
            return

        webhook = getattr(self.node, "tradingview_webhook", None)
        signal = str(getattr(webhook, "latest_signal", "") or "").strip()
        if signal:
            parts.append(f"TradingView signal: {signal}")

    async def _append_orderbook_context(self, parts: list[str]) -> None:
        if not bool(getattr(self.node, "orderbook_enabled", False)):
            return

        analyzers = getattr(self.node, "orderbook_analyzers", {})
        if not isinstance(analyzers, dict):
            return

        for symbol, analyzer in analyzers.items():
            try:
                update = getattr(analyzer, "update", None)
                if callable(update):
                    result = update()
                    if inspect.isawaitable(result):
                        await result

                get_context = getattr(analyzer, "get_context_string", None)
                if callable(get_context):
                    context = get_context()
                    if context:
                        parts.append(f"{symbol} OrderBook: {context}")
            except Exception as exc:
                logger.warning("Orderbook analyzer failed for %s/%s: %s", self.node.node_id, symbol, exc)

    def _append_market_context(self, parts: list[str]) -> None:
        market = getattr(self.node, "_last_market", None)
        if not isinstance(market, dict):
            return

        price_now = self._safe_float(market.get("price"), 0.0)
        price_prev1 = self._safe_float(getattr(self.node, "_prev_price", 0.0), 0.0)
        price_prev2 = self._safe_float(getattr(self.node, "_prev_prev_price", 0.0), 0.0)

        if price_now <= 0:
            return

        trend = "up" if price_now >= price_prev1 else "down"
        parts.append(
            f"price_now={price_now:.4f}, "
            f"price_prev1={price_prev1:.4f}, "
            f"price_prev2={price_prev2:.4f}, "
            f"trend={trend}"
        )

    def _append_node_context(self, parts: list[str]) -> None:
        parts.append(f"volatility={self._current_volatility():.3f}")
        parts.append(f"dq={self._current_dq():.3f}")
        parts.append(f"capital={self._safe_float(getattr(self.node, 'capital', 0.0), 0.0):.2f}")

        node_niche = getattr(self.node, "node_niche", None)
        if callable(node_niche):
            try:
                parts.append(f"niche={node_niche()}")
            except Exception:
                logger.debug("node_niche() failed for %s.", self.node.node_id, exc_info=True)

    def _append_memory_context(self, parts: list[str]) -> None:
        memory = getattr(self.node, "memory", None)
        find_similar = getattr(memory, "find_similar", None)
        if not callable(find_similar):
            return

        try:
            similar = find_similar(self._current_volatility(), self._current_dq(), top_k=3)
        except Exception as exc:
            logger.warning("Memory replay failed for %s: %s", self.node.node_id, exc)
            return

        if not similar:
            return

        lines = ["Past successful strategies in similar conditions:"]
        for index, record in enumerate(similar, start=1):
            if not isinstance(record, dict):
                continue
            params = record.get("params", {})
            fitness = self._safe_float(record.get("fitness"), 0.0)
            lines.append(f"{index}. params={params}, fitness={fitness:.4f}")

        if len(lines) > 1:
            parts.append("\n".join(lines))

    def _append_population_context(self, parts: list[str]) -> None:
        genetic_engine = getattr(self.node, "engine", None)
        population = getattr(genetic_engine, "population", None)
        fitness_func = getattr(genetic_engine, "_fitness", None)

        if not population or not callable(fitness_func):
            return

        try:
            top = sorted(
                [
                    genome
                    for genome in population
                    if hasattr(genome, "params")
                ],
                key=lambda genome: self._safe_float(fitness_func(genome.params), 0.0),
                reverse=True,
            )[:3]
        except Exception as exc:
            logger.warning("Population context failed for %s: %s", self.node.node_id, exc)
            return

        if not top:
            return

        lines = ["Top-3 genomes in population:"]
        for index, genome in enumerate(top, start=1):
            params = getattr(genome, "params", {})
            fitness = self._safe_float(fitness_func(params), 0.0)
            niche = getattr(genome, "niche", "N/A")
            lines.append(f"{index}. params={params}, fitness={fitness:.4f}, niche={niche}")

        parts.append("\n".join(lines))

    async def _publish_genome(self, genome_dict: dict[str, Any]) -> None:
        if bool(getattr(config, "gossip_signing_enabled", False)):
            await self._publish_signed_genome(genome_dict)
        else:
            await self._publish_unsigned_genome(genome_dict)

    async def _publish_signed_genome(self, genome_dict: dict[str, Any]) -> None:
        node_id = str(getattr(self.node, "node_id", "unknown"))
        required = (
            "gossip_seq_no",
            "gossip_lamport_ts",
            "gossip_public_bytes",
            "gossip_key_id",
            "gossip_private_key",
            "crdt",
        )

        if not all(hasattr(self.node, attr) for attr in required):
            logger.warning("Node %s missing gossip signing attrs; skipping signed genome publish.", node_id)
            return

        self.node.gossip_seq_no += 1
        self.node.gossip_lamport_ts += 1

        now_ms = int(time.time() * 1000)
        meta = {
            "envelope_version": "1.0",
            "domain": self.GOSSIP_DOMAIN,
            "payload_type": "memory.fact",
            "topic": "swarm.genome",
            "sender_peer_id": node_id,
            "sender_node_id": node_id,
            "sender_pubkey": self.node.gossip_public_bytes,
            "key_id": self.node.gossip_key_id,
            "key_version": 1,
            "seq_no": self.node.gossip_seq_no,
            "lamport_ts": self.node.gossip_lamport_ts,
            "nonce": os.urandom(16).hex(),
            "timestamp_ms": now_ms,
            "ttl_ms": self.GOSSIP_TTL_MS,
            "expires_at_ms": now_ms + self.GOSSIP_TTL_MS,
            "parent_hashes": [],
        }

        try:
            envelope = sign_envelope(genome_dict, meta, self.node.gossip_private_key)
            payload = envelope.model_dump(mode="json")
            await self._crdt_add(payload)
            logger.info("Node %s published signed champion genome to CRDT.", node_id)
        except Exception as exc:
            logger.exception("Node %s failed to sign/publish genome: %s", node_id, exc)

    async def _publish_unsigned_genome(self, genome_dict: dict[str, Any]) -> None:
        node_id = str(getattr(self.node, "node_id", "unknown"))
        crypto = getattr(self.node, "crypto", None)

        sign = getattr(crypto, "sign", None)
        public_key = getattr(crypto, "public_bytes_hex", "")
        if not callable(sign) or not public_key:
            logger.warning("Node %s missing crypto signer; publishing unsigned genome without signature.", node_id)
            await self._crdt_add(dict(genome_dict))
            return

        payload = dict(genome_dict)
        payload_for_sign = {
            "params": payload.get("params", {}),
            "fitness": payload.get("fitness", 0.0),
        }
        payload["signature"] = sign(payload_for_sign)
        payload["origin_pubkey"] = public_key

        await self._crdt_add(payload)
        logger.info("Node %s published champion genome to CRDT.", node_id)

    async def _crdt_add(self, payload: dict[str, Any]) -> None:
        crdt = getattr(self.node, "crdt", None)
        add_genome = getattr(crdt, "add_genome", None)
        if not callable(add_genome):
            logger.warning("Node %s CRDT lacks add_genome(); skipping publish.", self.node.node_id)
            return

        result = add_genome(payload)
        if inspect.isawaitable(result):
            await result

    def _get_base_params(self) -> dict[str, Any]:
        genetic_engine = getattr(self.node, "engine", None)
        champion = getattr(genetic_engine, "champion", None)
        if self._valid_champion(champion):
            return dict(champion[0])

        current_params = getattr(self.node, "current_params", None)
        if isinstance(current_params, dict):
            return dict(current_params)

        return {}

    def _params_to_genome(self, params: dict[str, Any]) -> Optional[GenomeProtocol]:
        dict_to_genome = getattr(self.node, "dict_to_genome", None)
        if not callable(dict_to_genome):
            return None

        try:
            return dict_to_genome({"params": dict(params)})
        except Exception as exc:
            logger.warning("dict_to_genome failed for %s: %s", self.node.node_id, exc)
            return None

    def _make_genome_dict(self, params: dict[str, Any], fitness: float) -> Optional[dict[str, Any]]:
        make_genome = getattr(self.node, "make_genome", None)
        if not callable(make_genome):
            return None

        try:
            genome = make_genome(dict(params), float(fitness))
        except Exception as exc:
            logger.warning("make_genome failed for %s: %s", self.node.node_id, exc)
            return None

        return dict(genome) if isinstance(genome, dict) else None

    def _apply_semantic_rules(self, params: dict[str, Any], volatility: float, dq: float) -> dict[str, Any]:
        semantic = getattr(self.node, "semantic", None)
        apply_rules = getattr(semantic, "apply_rules", None)
        if not callable(apply_rules):
            return dict(params)

        try:
            result = apply_rules(dict(params), volatility, dq)
            return dict(result) if isinstance(result, dict) else dict(params)
        except Exception as exc:
            logger.warning("Semantic rules failed for %s: %s", self.node.node_id, exc)
            return dict(params)

    def _is_champion_better(self, champion_params: dict[str, Any], champion_fitness: float) -> bool:
        genetic_engine = getattr(self.node, "engine", None)
        fitness_func = getattr(genetic_engine, "_fitness", None)
        current_params = getattr(self.node, "current_params", None)

        if not callable(fitness_func) or not isinstance(current_params, dict):
            return True

        try:
            current_fitness = self._safe_float(fitness_func(current_params), -1.0)
        except Exception:
            current_fitness = -1.0

        return champion_fitness > current_fitness

    def _add_champion_to_memory(
        self,
        *,
        params: dict[str, Any],
        fitness: float,
        volatility: float,
        dq: float,
    ) -> None:
        memory = getattr(self.node, "memory", None)
        add = getattr(memory, "add", None)
        if not callable(add):
            return

        try:
            add(
                market_volatility=volatility,
                dq=dq,
                capital=self._safe_float(getattr(self.node, "capital", 0.0), 0.0),
                params=dict(params),
                fitness=float(fitness),
                niche=self._node_niche(),
            )
        except Exception as exc:
            logger.warning("Memory add failed for %s: %s", self.node.node_id, exc)

    def _update_market_state(self, market: dict[str, Any]) -> None:
        previous_price = self._safe_float(getattr(self.node, "_prev_price", 0.0), 0.0)
        current_price = self._safe_float(market.get("price"), previous_price)

        self.node._prev_prev_price = previous_price
        self.node._prev_price = current_price
        self.node._last_market = dict(market)

    def _ensure_node_market_attrs(self) -> None:
        if not hasattr(self.node, "_prev_price"):
            self.node._prev_price = 0.0
        if not hasattr(self.node, "_prev_prev_price"):
            self.node._prev_prev_price = 0.0
        if not hasattr(self.node, "_last_market"):
            self.node._last_market = None

    def _current_volatility(self) -> float:
        getter = getattr(self.node, "_current_volatility", None)
        if not callable(getter):
            return 0.0

        try:
            return self._safe_float(getter(), 0.0)
        except Exception:
            return 0.0

    def _current_dq(self) -> float:
        survival = getattr(self.node, "survival", None)
        return self._safe_float(getattr(survival, "dq", 0.0), 0.0)

    def _node_niche(self) -> str:
        node_niche = getattr(self.node, "node_niche", None)
        if callable(node_niche):
            try:
                return str(node_niche())
            except Exception:
                return "N/A"
        return "N/A"

    @staticmethod
    def _valid_champion(champion: Any) -> bool:
        if not isinstance(champion, tuple) or len(champion) < 2:
            return False
        params, fitness = champion[0], champion[1]
        return isinstance(params, dict) and EvolutionEngine._safe_float(fitness, 0.0) > 0.0

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
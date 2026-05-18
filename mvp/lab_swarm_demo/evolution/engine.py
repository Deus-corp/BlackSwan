"""
Evolution Engine – мутации, генетика, memory replay.
"""
import logging
import time
import os
import asyncio
from typing import Any, Dict, Optional, List # Added type hints for better readability
from swarm_config import config
from sim.genetic_engine import Genome
from src.evolution.mutation_engine import MutationEngine
from src.security.gossip_envelope import sign_envelope
from src.economy.roi_dispatcher import ROIDispatcher
from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    Manages the evolutionary process for a swarm node, including LLM-driven mutations,
    genetic steps for population evolution, and memory-replay based context generation.
    """
    def __init__(self, node: Any) -> None:
        """
        Initializes the EvolutionEngine with a reference to the SwarmNode.

        Args:
            node: A reference to the SwarmNode instance. This object is expected to
                  provide access to various components like LLM, mutation engine,
                  market data, memory, genetic engine, survival metrics, etc.
        """
        self.node = node          # ссылка на SwarmNode для доступа к его методам
        self.llm = node.llm
        self.mutation_engine: MutationEngine = node.mutation_engine # Added type hint for clarity

    async def tick(self, market: Dict[str, Any]) -> None:
        """
        Executes one step of the evolution process. Called periodically from the main loop.

        This method orchestrates LLM mutations, genetic steps, and updates market-related
        price tracking attributes on the node based on the current market snapshot.

        Args:
            market: A dictionary containing market data for the current step.
                    It is expected to have a 'price' key.
        """
        step: int = self.node.step_count # Added type hint
        # LLM Mutation & Memory replay (раз в 100 шагов)
        if step % 100 == 0:
            await self._mutate_with_context()

        # Генетический шаг (раз в 50 шагов)
        if step % 50 == 0:
            self._genetic_step()

        # Обновление цен
        self.node._prev_prev_price = self.node._prev_price
        if market:
            self.node._prev_price = market.get("price", self.node._prev_price)

    async def _mutate_with_context(self) -> None:
        """
        Performs an LLM-driven mutation, gathering various contextual information
        to inform the mutation process.

        Context sources include:
        - External research (internet researcher, TradingView signals, order book analysis).
        - Market context (current and historical prices, trend).
        - Node's internal state (volatility, DQ score, capital, niche).
        - Memory replay of similar past successful strategies.
        - Top-performing genomes from the current population.

        The gathered context is then passed to the LLM mutation engine.
        """
        # --- Сбор внешнего контекста (новости, сигналы, ордербук) ---
        external_context: str = ""
        if config.internet_researcher_enabled:
            try:
                external_context = await self.node.internet_researcher.gather_context()
            except Exception as e:
                logger.warning(f"Internet researcher failed to gather context: {e}")
                external_context = "" # Reset context on failure
        if self.node.tradingview_enabled and self.node.tradingview_webhook.latest_signal:
            signal: str = self.node.tradingview_webhook.latest_signal # Added type hint
            external_context += f"\nTradingView signal: {signal}\n"
        if self.node.orderbook_enabled:
            for sym, analyzer in self.node.orderbook_analyzers.items():
                metrics = await analyzer.update()
                if metrics:
                    external_context += f"\n{sym} OrderBook: {analyzer.get_context_string()}"

        # --- Расширенный рыночный контекст ---
        market_context: str = ""
        m: Optional[Dict[str, Any]] = getattr(self.node, '_last_market', None) # Added type hint
        if m:
            price: float = m.get('price', 0.0) # Added type hint, default to float
            prev1: float = getattr(self.node, '_prev_price', price) # Added type hint
            prev2: float = getattr(self.node, '_prev_prev_price', price) # Added type hint
            trend: str = "up" if price >= prev1 else "down" # Added type hint
            market_context = (
                f"price_now={price:.4f}, "
                f"price_prev1={prev1:.4f}, "
                f"price_prev2={prev2:.4f}, "
                f"trend={trend}, "
            )

        # --- Базовый контекст узла ---
        context: str = ( # Added type hint
            f"volatility={self.node._current_volatility():.3f}, "
            f"dq={self.node.survival.dq:.3f}, "
            f"capital={self.node.capital:.2f}, "
            f"niche={self.node.node_niche()}, "
        )
        if market_context:
            context += market_context
        if external_context:
            context += "\n" + external_context

        # --- Memory replay: похожие успешные стратегии ---
        if len(self.node.memory) > 0:
            vol: float = self.node._current_volatility() # Added type hint
            similar: Optional[List[Dict[str, Any]]] = self.node.memory.find_similar(vol, self.node.survival.dq, top_k=3) # Added type hint
            if similar:
                memory_lines: List[str] = ["Past successful strategies in similar conditions:"]
                for i, rec in enumerate(similar):
                    params: Dict[str, Any] = rec.get("params", {}) # Added type hint
                    fitness: float = rec.get("fitness", 0.0) # Added type hint
                    memory_lines.append(f"{i+1}. params={params}, fitness={fitness:.4f}")
                memory_context: str = "\n".join(memory_lines) # Added type hint
                context += "\n" + memory_context

        # --- Топ-3 гена популяции ---
        if self.node.engine.population:
            # Filter for actual Genome instances and sort by fitness (descending)
            top_genomes: List[Genome] = sorted( # Added type hint
                [g for g in self.node.engine.population if isinstance(g, Genome)],
                key=lambda g: self.node.engine._fitness(g.params),
                reverse=True
            )[:3]
            if top_genomes:
                top_lines: List[str] = ["Top-3 genomes in population:"] # Added type hint
                for i, g in enumerate(top_genomes):
                    top_lines.append(
                        f"{i+1}. params={g.params}, fitness={self.node.engine._fitness(g.params):.4f}, niche={g.niche}"
                    )
                context += "\n" + "\n".join(top_lines)

        # --- Вызов LLM мутации ---
        # Ensure champion exists before accessing its elements
        champion_params: Dict[str, Any] = self.node.engine.champion[0] if self.node.engine.champion else self.node.current_params # Added type hint
        new_params: Dict[str, Any] = self.mutation_engine.mutate(champion_params, context) # Added type hint
        if new_params != champion_params:
            genome: Genome = self.node.dict_to_genome({"params": new_params}) # Added type hint
            self.node.engine.add_genome(genome)
            # BUG FIX: Removed redundant import. note_llm_mutation is already imported at the top.
            # from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation
            note_llm_mutation()
            
    def _genetic_step(self) -> None:
        """
        Executes one genetic evolution step for the node's population.

        This involves evolving a new generation, evaluating the champion,
        and potentially publishing the champion's genome to the CRDT
        (with or without gossip signing). If the new champion is superior
        to the node's current parameters, the node's parameters and dispatcher
        are updated. The champion's performance is also added to the node's memory.
        """
        self.node.engine.evolve_generation()
        # Ensure a champion exists and has a positive fitness before proceeding
        if self.node.engine.champion and self.node.engine.champion[1] > 0:
            current_vol: float = self.node._current_volatility()
            # Apply semantic rules to the champion's parameters before publishing
            params_to_publish: Dict[str, Any] = self.node.semantic.apply_rules(
                self.node.engine.champion[0], current_vol, self.node.survival.dq
            )
            genome_dict: Dict[str, Any] = self.node.make_genome(params_to_publish, self.node.engine.champion[1])

            if config.gossip_signing_enabled:
                self.node.gossip_seq_no += 1
                self.node.gossip_lamport_ts += 1
                meta: Dict[str, Any] = { # Added type hint
                    "envelope_version": "1.0",
                    "domain": "blackswan-gossip-v1",
                    "payload_type": "memory.fact",
                    "topic": "swarm.genome",
                    "sender_peer_id": self.node.node_id,
                    "sender_node_id": self.node.node_id,
                    "sender_pubkey": self.node.gossip_public_bytes,
                    "key_id": self.node.gossip_key_id,
                    "key_version": 1,
                    "seq_no": self.node.gossip_seq_no,
                    "lamport_ts": self.node.gossip_lamport_ts,
                    "nonce": os.urandom(16).hex(),
                    "timestamp_ms": int(time.time() * 1000),
                    "ttl_ms": 60000,
                    "expires_at_ms": int(time.time() * 1000) + 60000,
                    "parent_hashes": [],
                }
                envelope = sign_envelope(genome_dict, meta, self.node.gossip_private_key)
                asyncio.create_task(self.node.crdt.add_genome(envelope.model_dump(mode='json')))
            else:
                payload: Dict[str, Any] = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]} # Added type hint
                genome_dict["signature"] = self.node.crypto.sign(payload)
                genome_dict["origin_pubkey"] = self.node.crypto.public_bytes_hex
                asyncio.create_task(self.node.crdt.add_genome(genome_dict))

            # Update node's current parameters and dispatcher if the champion is better
            # Ensure champion exists before comparing fitness
            if self.node.engine.champion and self.node.engine.champion[1] > self.node.engine._fitness(self.node.current_params):
                self.node.current_params = self.node.engine.champion[0]
                self.node.dispatcher = ROIDispatcher(config=self.node.current_params)

            # Add champion's performance to node's memory
            # Ensure champion exists before adding to memory
            if self.node.engine.champion:
                self.node.memory.add(
                    market_volatility=current_vol,
                    dq=self.node.survival.dq,
                    capital=self.node.capital,
                    params=self.node.engine.champion[0],
                    fitness=self.node.engine.champion[1],
                )
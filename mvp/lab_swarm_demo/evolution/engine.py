"""
Evolution Engine – orchestrates mutations, genetics, and memory replay for swarm nodes.
"""
import logging
import time
import os
import asyncio
from typing import Any, Dict, Optional, List, Tuple

# Assuming these are available in the environment/project structure
from swarm_config import config
from sim.genetic_engine import Genome
from src.evolution.mutation_engine import MutationEngine
from src.security.gossip_envelope import sign_envelope # Assuming sign_envelope expects payload, meta, and private_key
from src.economy.roi_dispatcher import ROIDispatcher
from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    Manages the evolutionary process for a swarm node, including LLM-driven mutations,
    genetic steps for population evolution, and memory-replay based context generation.

    This engine orchestrates how a node adapts its parameters over time, incorporating
    external market data, internal performance metrics, historical memory, and
    population-level genetic evolution.
    """
    node: Any
    llm: Any
    mutation_engine: MutationEngine

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
        self.mutation_engine = node.mutation_engine

        # Ensure _prev_price and _prev_prev_price are initialized on the node
        # This prevents potential AttributeError on the first tick if not set by SwarmNode __init__
        if not hasattr(self.node, '_prev_price'):
            self.node._prev_price = 0.0
        if not hasattr(self.node, '_prev_prev_price'):
            self.node._prev_prev_price = 0.0
        if not hasattr(self.node, '_last_market'):
            self.node._last_market = None

    async def tick(self, market: Dict[str, Any]) -> None:
        """
        Executes one step of the evolution process. Called periodically from the main loop.

        This method orchestrates LLM mutations, genetic steps, and updates market-related
        price tracking attributes on the node based on the current market snapshot.

        Args:
            market: A dictionary containing market data for the current step.
                    It is expected to have a 'price' key (e.g., {'price': 123.45}).
        """
        step: int = self.node.step_count

        # LLM Mutation & Memory replay (раз в 100 шагов)
        if step > 0 and step % 100 == 0:
            logger.debug(f"Node {self.node.node_id} performing LLM mutation at step {step}")
            await self._mutate_with_context()

        # Генетический шаг (раз в 50 шагов)
        if step > 0 and step % 50 == 0:
            logger.debug(f"Node {self.node.node_id} performing genetic step at step {step}")
            self._genetic_step()

        # Обновление цен
        self.node._prev_prev_price = self.node._prev_price
        if market:
            current_price: float = market.get("price", self.node._prev_price)
            self.node._prev_price = current_price
            self.node._last_market = market # Ensure _last_market is always updated

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
        logger.info(f"Node {self.node.node_id} gathering context for LLM mutation.")
        
        context_parts: List[str] = []

        # --- Сбор внешнего контекста (новости, сигналы, ордербук) ---
        if config.internet_researcher_enabled and hasattr(self.node, 'internet_researcher'):
            try:
                research_context: str = await self.node.internet_researcher.gather_context()
                if research_context:
                    context_parts.append(research_context)
            except Exception as e:
                logger.warning(f"Internet researcher failed to gather context for node {self.node.node_id}: {e}")

        if getattr(self.node, 'tradingview_enabled', False) and hasattr(self.node, 'tradingview_webhook') and self.node.tradingview_webhook.latest_signal:
            signal: str = self.node.tradingview_webhook.latest_signal
            context_parts.append(f"TradingView signal: {signal}")

        if getattr(self.node, 'orderbook_enabled', False) and hasattr(self.node, 'orderbook_analyzers'):
            for sym, analyzer in self.node.orderbook_analyzers.items():
                try:
                    await analyzer.update() # Update analyzer state
                    context_string = analyzer.get_context_string()
                    if context_string:
                        context_parts.append(f"{sym} OrderBook: {context_string}")
                except Exception as e:
                    logger.warning(f"Orderbook analyzer for {sym} failed for node {self.node.node_id}: {e}")

        # --- Расширенный рыночный контекст ---
        m: Optional[Dict[str, Any]] = getattr(self.node, '_last_market', None)
        current_price: float = m.get('price', 0.0) if m else 0.0
        prev1_price: float = getattr(self.node, '_prev_price', current_price)
        prev2_price: float = getattr(self.node, '_prev_prev_price', current_price)

        if current_price:
            trend: str = "up" if current_price >= prev1_price else "down"
            context_parts.append(
                f"price_now={current_price:.4f}, "
                f"price_prev1={prev1_price:.4f}, "
                f"price_prev2={prev2_price:.4f}, "
                f"trend={trend}"
            )

        # --- Базовый контекст узла ---
        if hasattr(self.node, '_current_volatility') and callable(self.node._current_volatility):
            context_parts.append(f"volatility={self.node._current_volatility():.3f}")
        if hasattr(self.node, 'survival') and hasattr(self.node.survival, 'dq'):
            context_parts.append(f"dq={self.node.survival.dq:.3f}")
        if hasattr(self.node, 'capital'):
            context_parts.append(f"capital={self.node.capital:.2f}")
        if hasattr(self.node, 'node_niche') and callable(self.node.node_niche):
            context_parts.append(f"niche={self.node.node_niche()}")

        # --- Memory replay: похожие успешные стратегии ---
        if hasattr(self.node, 'memory') and len(self.node.memory) > 0:
            current_volatility: float = getattr(self.node, '_current_volatility', lambda: 0.0)()
            current_dq: float = getattr(self.node.survival, 'dq', 0.0) if hasattr(self.node, 'survival') else 0.0

            similar_strategies: Optional[List[Dict[str, Any]]] = self.node.memory.find_similar(
                current_volatility, current_dq, top_k=3
            )
            if similar_strategies:
                memory_lines: List[str] = ["Past successful strategies in similar conditions:"]
                for i, rec in enumerate(similar_strategies):
                    params_mem: Dict[str, Any] = rec.get("params", {})
                    fitness_mem: float = rec.get("fitness", 0.0)
                    memory_lines.append(f"{i+1}. params={params_mem}, fitness={fitness_mem:.4f}")
                context_parts.append("\n".join(memory_lines))

        # --- Топ-3 гена популяции ---
        if hasattr(self.node, 'engine') and hasattr(self.node.engine, 'population') and self.node.engine.population:
            if hasattr(self.node.engine, '_fitness') and callable(self.node.engine._fitness):
                top_genomes: List[Genome] = sorted(
                    [g for g in self.node.engine.population if isinstance(g, Genome)],
                    key=lambda g: self.node.engine._fitness(g.params),
                    reverse=True
                )[:3]
                if top_genomes:
                    top_lines: List[str] = ["Top-3 genomes in population:"]
                    for i, g in enumerate(top_genomes):
                        top_lines.append(
                            f"{i+1}. params={g.params}, fitness={self.node.engine._fitness(g.params):.4f}, niche={getattr(g, 'niche', 'N/A')}"
                        )
                    context_parts.append("\n".join(top_lines))
            else:
                logger.warning(f"Genetic engine _fitness method not found or not callable for node {self.node.node_id}.")

        full_context: str = "\n".join(context_parts)

        # --- Вызов LLM мутации ---
        champion_params: Dict[str, Any]
        if hasattr(self.node, 'engine') and self.node.engine.champion:
            champion_params = self.node.engine.champion[0]
        elif hasattr(self.node, 'current_params'):
            champion_params = self.node.current_params
            logger.warning(f"Node {self.node.node_id} has no champion in engine, using current_params for mutation.")
        else:
            logger.error(f"Node {self.node.node_id} has no champion or current_params to mutate from. Skipping mutation.")
            return # Cannot mutate without a base parameter set

        logger.info(f"Node {self.node.node_id} calling LLM for mutation with context length {len(full_context)}.")
        new_params: Dict[str, Any] = self.mutation_engine.mutate(champion_params, full_context)

        if new_params != champion_params:
            logger.info(f"Node {self.node.node_id} successfully mutated parameters.")
            if hasattr(self.node, 'dict_to_genome') and callable(self.node.dict_to_genome):
                genome_from_dict: Genome = self.node.dict_to_genome({"params": new_params})
                if hasattr(self.node.engine, 'add_genome') and callable(self.node.engine.add_genome):
                    self.node.engine.add_genome(genome_from_dict)
                    note_llm_mutation() # This function is imported at the top, no need for redundant import
                else:
                    logger.error(f"Node {self.node.node_id} genetic engine lacks 'add_genome' method.")
            else:
                logger.error(f"Node {self.node.node_id} lacks 'dict_to_genome' method to convert new params to genome.")
        else:
            logger.info(f"Node {self.node.node_id} LLM mutation resulted in no change.")
            
    def _genetic_step(self) -> None:
        """
        Executes one genetic evolution step for the node's population.

        This involves evolving a new generation, evaluating the champion,
        and potentially publishing the champion's genome to the CRDT
        (with or without gossip signing). If the new champion is superior
        to the node's current parameters, the node's parameters and dispatcher
        are updated. The champion's performance is also added to the node's memory.
        """
        logger.info(f"Node {self.node.node_id} performing genetic evolution step.")

        if not (hasattr(self.node, 'engine') and hasattr(self.node.engine, 'evolve_generation') and callable(self.node.engine.evolve_generation)):
            logger.error(f"Node {self.node.node_id} genetic engine lacks 'evolve_generation' method. Skipping genetic step.")
            return

        self.node.engine.evolve_generation()

        # Ensure a champion exists and has a positive fitness before proceeding
        # self.node.engine.champion is expected to be a tuple (params: Dict, fitness: float)
        champion: Optional[Tuple[Dict[str, Any], float]] = self.node.engine.champion

        if champion is None or champion[1] <= 0:
            logger.debug(f"Node {self.node.node_id} has no champion or non-positive champion fitness ({champion[1] if champion else 'N/A'}). Skipping publish and update.")
            return

        champion_params: Dict[str, Any] = champion[0]
        champion_fitness: float = champion[1]

        current_volatility: float = getattr(self.node, '_current_volatility', lambda: 0.0)()
        current_dq: float = getattr(self.node.survival, 'dq', 0.0) if hasattr(self.node, 'survival') else 0.0

        # Apply semantic rules to the champion's parameters before publishing
        params_to_publish: Dict[str, Any]
        if hasattr(self.node, 'semantic') and hasattr(self.node.semantic, 'apply_rules') and callable(self.node.semantic.apply_rules):
            params_to_publish = self.node.semantic.apply_rules(
                champion_params, current_volatility, current_dq
            )
        else:
            logger.warning(f"Node {self.node.node_id} lacks 'semantic' object or 'apply_rules' method. Publishing raw champion params.")
            params_to_publish = champion_params

        if not (hasattr(self.node, 'make_genome') and callable(self.node.make_genome)):
            logger.error(f"Node {self.node.node_id} lacks 'make_genome' method. Cannot publish genome.")
            return

        genome_dict: Dict[str, Any] = self.node.make_genome(params_to_publish, champion_fitness)
        
        if config.gossip_signing_enabled:
            # Ensure necessary attributes for gossip are present
            required_gossip_attrs = [
                'gossip_seq_no', 'gossip_lamport_ts', 'node_id', 'gossip_public_bytes',
                'gossip_key_id', 'gossip_private_key', 'crdt'
            ]
            if not all(hasattr(self.node, attr) for attr in required_gossip_attrs):
                logger.error(f"Node {self.node.node_id} missing attributes for gossip signing. Skipping genome publish.")
                return

            self.node.gossip_seq_no += 1
            self.node.gossip_lamport_ts += 1
            meta: Dict[str, Any] = {
                "envelope_version": "1.0",
                "domain": "blackswan-gossip-v1",
                "payload_type": "memory.fact",
                "topic": "swarm.genome",
                "sender_peer_id": self.node.node_id,
                "sender_node_id": self.node.node_id,
                "sender_pubkey": self.node.gossip_public_bytes, # Expected to be bytes or hex string, `sign_envelope` usually expects bytes for signing, `meta` field may be hex
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
            try:
                envelope_signed = sign_envelope(genome_dict, meta, self.node.gossip_private_key)
                if hasattr(self.node.crdt, 'add_genome') and callable(self.node.crdt.add_genome):
                    asyncio.create_task(self.node.crdt.add_genome(envelope_signed.model_dump(mode='json')))
                    logger.info(f"Node {self.node.node_id} published signed champion genome to CRDT.")
                else:
                    logger.error(f"Node {self.node.node_id} CRDT lacks 'add_genome' method. Cannot publish genome.")
            except Exception as e:
                logger.error(f"Failed to sign and publish genome for node {self.node.node_id} with gossip: {e}", exc_info=True)
        else:
            required_unsigned_attrs = ['crypto', 'crdt']
            if not all(hasattr(self.node, attr) for attr in required_unsigned_attrs) or \
               not (hasattr(self.node.crypto, 'sign') and hasattr(self.node.crypto, 'public_bytes_hex')):
                logger.error(f"Node {self.node.node_id} missing crypto or CRDT attributes for unsigned publish. Skipping genome publish.")
                return

            payload_for_sign: Dict[str, Any] = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]}
            genome_dict["signature"] = self.node.crypto.sign(payload_for_sign)
            genome_dict["origin_pubkey"] = self.node.crypto.public_bytes_hex
            if hasattr(self.node.crdt, 'add_genome') and callable(self.node.crdt.add_genome):
                asyncio.create_task(self.node.crdt.add_genome(genome_dict))
                logger.info(f"Node {self.node.node_id} published unsigned champion genome to CRDT.")
            else:
                logger.error(f"Node {self.node.node_id} CRDT lacks 'add_genome' method. Cannot publish genome.")

        # Update node's current parameters and dispatcher if the champion is better
        current_params_fitness: float = -1.0 # Default if _fitness is not available or current_params is not set
        if (hasattr(self.node, 'current_params') and
                hasattr(self.node.engine, '_fitness') and callable(self.node.engine._fitness)):
            current_params_fitness = self.node.engine._fitness(self.node.current_params)

        if champion_fitness > current_params_fitness:
            self.node.current_params = champion_params
            self.node.dispatcher = ROIDispatcher(config=self.node.current_params) # Assuming ROIDispatcher takes config as a dict
            logger.info(f"Node {self.node.node_id} updated current parameters to new champion (fitness {champion_fitness:.4f}).")
        else:
            logger.debug(f"Node {self.node.node_id} champion (fitness={champion_fitness:.4f}) not superior to current params (fitness={current_params_fitness:.4f}). No parameter update.")

        # Add champion's performance to node's memory
        if hasattr(self.node, 'memory') and hasattr(self.node.memory, 'add') and callable(self.node.memory.add):
            self.node.memory.add(
                market_volatility=current_volatility,
                dq=current_dq,
                capital=getattr(self.node, 'capital', 0.0), # Use getattr for safety
                params=champion_params,
                fitness=champion_fitness,
            )
            logger.debug(f"Node {self.node.node_id} added champion to memory.")
        else:
            logger.warning(f"Node {self.node.node_id} lacks 'memory' object or 'add' method. Cannot add champion to memory.")
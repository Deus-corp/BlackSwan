"""
Evolution Engine – orchestrates mutations, genetics, and memory replay for swarm nodes.
"""
import logging
import time
import os
import asyncio
from typing import Any, Dict, Optional, List, Tuple, Callable, Union, Protocol

# Assuming these are available in the environment/project structure
from swarm_config import config

# Dummy classes/protocols for external dependencies to aid type checking
# In a real project, these would be properly imported or defined in a shared place.
class Genome:
    """Represents a genetic genome with parameters and optional niche/fitness."""
    params: Dict[str, Any]
    fitness: float
    niche: str
    def __init__(self, params: Dict[str, Any], fitness: float = 0.0, niche: str = "default") -> None:
        self.params = params
        self.fitness = fitness
        self.niche = niche
    def __repr__(self) -> str:
        return f"Genome(params={self.params}, fitness={self.fitness:.4f}, niche='{self.niche}')"

class MutationEngine:
    """Dummy MutationEngine for type hinting, expected to have a mutate method."""
    def mutate(self, base_params: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Mutates parameters based on context."""
        return base_params

class ROIDispatcher:
    """Dummy ROIDispatcher for type hinting, expected to take a config dict."""
    def __init__(self, config: Dict[str, Any]) -> None:
        pass

class GossipEnvelopeModel:
    """Dummy Pydantic-like model for a signed gossip envelope."""
    def model_dump(self, mode: str = 'json') -> Dict[str, Any]:
        """Converts the model to a dictionary suitable for JSON serialization."""
        # This is a placeholder; actual implementation would depend on the Pydantic model structure
        return {"payload": {}, "meta": {}, "signature": ""}

# Assuming sign_envelope and other external types from src.security.gossip_envelope
# and src.economy.roi_dispatcher. `type: ignore` is used because these are external
# and their exact definitions are not provided in this context.
from src.security.gossip_envelope import sign_envelope # type: ignore
from src.economy.roi_dispatcher import ROIDispatcher # type: ignore
from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation

logger = logging.getLogger(__name__)


class SwarmNodeProtocol(Protocol):
    """
    Protocol for the SwarmNode, defining expected attributes and methods
    accessed by the EvolutionEngine. This helps with type hinting the `node` object.
    """
    node_id: str
    step_count: int
    llm: Any # Assuming generic LLM client interface
    mutation_engine: MutationEngine
    _prev_price: float
    _prev_prev_price: float
    _last_market: Optional[Dict[str, Any]]
    internet_researcher: Any # Expected to have async gather_context()
    tradingview_enabled: bool
    tradingview_webhook: Any # Expected to have latest_signal: str
    orderbook_enabled: bool
    orderbook_analyzers: Dict[str, Any] # Each analyzer expected to have async update(), get_context_string()
    _current_volatility: Callable[[], float]
    survival: Any # Expected to have dq: float
    capital: float
    node_niche: Callable[[], str]
    memory: Any # Expected to have find_similar(volatility, dq, top_k), add(market_volatility, dq, capital, params, fitness, niche)
    engine: Any # Expected to have population, champion (tuple), evolve_generation(), _fitness(params), add_genome(genome)
    dict_to_genome: Callable[[Dict[str, Any]], Genome]
    make_genome: Callable[[Dict[str, Any], float], Dict[str, Any]]
    current_params: Dict[str, Any]
    dispatcher: ROIDispatcher
    crdt: Any # Expected to have async add_genome(genome_data)
    crypto: Any # Expected to have sign(payload), public_bytes_hex (str)
    gossip_seq_no: int
    gossip_lamport_ts: int
    gossip_public_bytes: Union[bytes, str] # Can be bytes for signing, hex string for meta
    gossip_key_id: str
    gossip_private_key: Union[bytes, str] # Can be bytes for signing, hex string for meta


class EvolutionEngine:
    """
    Manages the evolutionary process for a swarm node, including LLM-driven mutations,
    genetic steps for population evolution, and memory-replay based context generation.

    This engine orchestrates how a node adapts its parameters over time, incorporating
    external market data, internal performance metrics, historical memory, and
    population-level genetic evolution.
    """
    node: SwarmNodeProtocol
    llm: Any
    mutation_engine: MutationEngine

    def __init__(self, node: SwarmNodeProtocol) -> None:
        """
        Initializes the EvolutionEngine with a reference to the SwarmNode.

        Ensures critical market-related attributes (`_prev_price`, `_prev_prev_price`,
        `_last_market`) are initialized on the node to prevent `AttributeError`
        during the first `tick` or `_mutate_with_context` call.

        Args:
            node: A reference to the SwarmNode instance, adhering to the `SwarmNodeProtocol`.
                  This object is expected to provide access to various components like
                  LLM, mutation engine, market data, memory, genetic engine, survival metrics, etc.
        """
        self.node = node
        self.llm = node.llm
        self.mutation_engine = node.mutation_engine

        # Ensure _prev_price, _prev_prev_price, and _last_market are initialized on the node
        # This prevents potential AttributeError on the first tick or context gathering
        if not hasattr(self.node, '_prev_price'):
            self.node._prev_price = 0.0
        if not hasattr(self.node, '_prev_prev_price'):
            self.node._prev_prev_price = 0.0
        if not hasattr(self.node, '_last_market'):
            self.node._last_market = None

        logger.debug(f"EvolutionEngine initialized for node {self.node.node_id}.")


    async def tick(self, market: Dict[str, Any]) -> None:
        """
        Executes one step of the evolution process for the node. Called periodically.

        This method orchestrates LLM mutations, genetic steps, and updates market-related
        price tracking attributes on the node based on the current market snapshot.

        Args:
            market: A dictionary containing market data for the current step.
                    It is expected to contain at least a 'price' key (e.g., {'price': 123.45}).
        """
        step: int = self.node.step_count
        node_id: str = self.node.node_id

        # LLM Mutation & Memory replay (every 100 steps)
        if step > 0 and step % 100 == 0:
            logger.debug(f"Node {node_id} performing LLM mutation at step {step}")
            await self._mutate_with_context()

        # Genetic step (every 50 steps)
        if step > 0 and step % 50 == 0:
            logger.debug(f"Node {node_id} performing genetic step at step {step}")
            self._genetic_step()

        # Update prices
        self.node._prev_prev_price = self.node._prev_price
        current_price: float = market.get("price", self.node._prev_price)
        self.node._prev_price = current_price
        self.node._last_market = market # Ensure _last_market is always updated
        logger.debug(f"Node {node_id} updated prices: current={current_price:.4f}, prev={self.node._prev_price:.4f}, prev_prev={self.node._prev_prev_price:.4f}")


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
        If a new, different parameter set is generated, it's added to the genetic
        engine's population and a mutation metric is noted.
        """
        node_id: str = self.node.node_id
        logger.info(f"Node {node_id} gathering context for LLM mutation.")

        context_parts: List[str] = []

        # --- Gather external context (news, signals, order book) ---
        if config.internet_researcher_enabled and hasattr(self.node, 'internet_researcher'):
            researcher = getattr(self.node, 'internet_researcher')
            if hasattr(researcher, 'gather_context') and callable(researcher.gather_context):
                try:
                    research_context: str = await researcher.gather_context()
                    if research_context:
                        context_parts.append(research_context)
                        logger.debug(f"Node {node_id} added internet research context.")
                except Exception as e:
                    logger.warning(f"Internet researcher failed to gather context for node {node_id}: {type(e).__name__}: {e}")

        if getattr(self.node, 'tradingview_enabled', False) and hasattr(self.node, 'tradingview_webhook'):
            webhook = getattr(self.node, 'tradingview_webhook')
            if hasattr(webhook, 'latest_signal') and isinstance(webhook.latest_signal, str) and webhook.latest_signal:
                signal: str = webhook.latest_signal
                context_parts.append(f"TradingView signal: {signal}")
                logger.debug(f"Node {node_id} added TradingView signal context.")

        if getattr(self.node, 'orderbook_enabled', False) and hasattr(self.node, 'orderbook_analyzers'):
            orderbook_analyzers: Dict[str, Any] = getattr(self.node, 'orderbook_analyzers')
            for sym, analyzer in orderbook_analyzers.items():
                try:
                    if hasattr(analyzer, 'update') and callable(analyzer.update):
                        await analyzer.update() # Update analyzer state
                    if hasattr(analyzer, 'get_context_string') and callable(analyzer.get_context_string):
                        context_string: str = analyzer.get_context_string()
                        if context_string:
                            context_parts.append(f"{sym} OrderBook: {context_string}")
                            logger.debug(f"Node {node_id} added orderbook context for {sym}.")
                except Exception as e:
                    logger.warning(f"Orderbook analyzer for {sym} failed for node {node_id}: {type(e).__name__}: {e}")

        # --- Extended market context ---
        m: Optional[Dict[str, Any]] = self.node._last_market
        current_price: float = m.get('price', 0.0) if m else 0.0
        prev1_price: float = self.node._prev_price
        prev2_price: float = self.node._prev_prev_price

        if current_price:
            trend: str = "up" if current_price >= prev1_price else "down"
            context_parts.append(
                f"price_now={current_price:.4f}, "
                f"price_prev1={prev1_price:.4f}, "
                f"price_prev2={prev2_price:.4f}, "
                f"trend={trend}"
            )
            logger.debug(f"Node {node_id} added market price context.")

        # --- Node's basic context ---
        node_volatility_func: Optional[Callable[[], float]] = getattr(self.node, '_current_volatility', None)
        if node_volatility_func and callable(node_volatility_func):
            context_parts.append(f"volatility={node_volatility_func():.3f}")

        node_survival = getattr(self.node, 'survival', None)
        if node_survival and hasattr(node_survival, 'dq'):
            context_parts.append(f"dq={node_survival.dq:.3f}")

        node_capital: float = getattr(self.node, 'capital', 0.0)
        context_parts.append(f"capital={node_capital:.2f}")

        node_niche_func: Optional[Callable[[], str]] = getattr(self.node, 'node_niche', None)
        if node_niche_func and callable(node_niche_func):
            context_parts.append(f"niche={node_niche_func()}")
        logger.debug(f"Node {node_id} added node internal state context.")

        # --- Memory replay: similar successful strategies ---
        node_memory = getattr(self.node, 'memory', None)
        if node_memory and hasattr(node_memory, 'find_similar') and callable(node_memory.find_similar):
            current_volatility_val: float = node_volatility_func() if node_volatility_func else 0.0
            current_dq_val: float = getattr(node_survival, 'dq', 0.0) if node_survival else 0.0

            similar_strategies: Optional[List[Dict[str, Any]]] = node_memory.find_similar(
                current_volatility_val, current_dq_val, top_k=3
            )
            if similar_strategies:
                memory_lines: List[str] = ["Past successful strategies in similar conditions:"]
                for i, rec in enumerate(similar_strategies):
                    params_mem: Dict[str, Any] = rec.get("params", {})
                    fitness_mem: float = rec.get("fitness", 0.0)
                    memory_lines.append(f"{i+1}. params={params_mem}, fitness={fitness_mem:.4f}")
                context_parts.append("\n".join(memory_lines))
                logger.debug(f"Node {node_id} added memory replay context.")

        # --- Top-3 genes of the population ---
        genetic_engine = getattr(self.node, 'engine', None)
        if genetic_engine and hasattr(genetic_engine, 'population') and genetic_engine.population:
            if hasattr(genetic_engine, '_fitness') and callable(genetic_engine._fitness):
                fitness_func: Callable[[Dict[str, Any]], float] = genetic_engine._fitness
                # Filter for actual Genome instances and sort
                top_genomes: List[Genome] = sorted(
                    [g for g in genetic_engine.population if isinstance(g, Genome)],
                    key=lambda g: fitness_func(g.params),
                    reverse=True
                )[:3]
                if top_genomes:
                    top_lines: List[str] = ["Top-3 genomes in population:"]
                    for i, g in enumerate(top_genomes):
                        top_lines.append(
                            f"{i+1}. params={g.params}, fitness={fitness_func(g.params):.4f}, niche={getattr(g, 'niche', 'N/A')}"
                        )
                    context_parts.append("\n".join(top_lines))
                    logger.debug(f"Node {node_id} added top genomes context.")
            else:
                logger.warning(f"Genetic engine _fitness method not found or not callable for node {node_id}. Cannot get top genomes fitness.")

        full_context: str = "\n".join(context_parts)
        if not full_context:
            logger.warning(f"Node {node_id} generated empty context for LLM mutation. This may lead to suboptimal mutation.")

        # --- Call LLM mutation ---
        champion_params: Dict[str, Any]
        if genetic_engine and getattr(genetic_engine, 'champion', None):
            champion_params = genetic_engine.champion[0]
            logger.debug(f"Node {node_id} using engine's champion params as base for mutation.")
        elif hasattr(self.node, 'current_params') and self.node.current_params is not None:
            champion_params = self.node.current_params
            logger.warning(f"Node {node_id} has no champion in engine, using current_params for mutation.")
        else:
            logger.error(f"Node {node_id} has no champion or current_params to mutate from. Skipping mutation.")
            return # Cannot mutate without a base parameter set

        logger.info(f"Node {node_id} calling LLM for mutation with context length {len(full_context)}.")
        new_params: Dict[str, Any] = self.mutation_engine.mutate(champion_params, full_context)

        if new_params != champion_params:
            logger.info(f"Node {node_id} successfully mutated parameters.")
            dict_to_genome_func: Optional[Callable[[Dict[str, Any]], Genome]] = getattr(self.node, 'dict_to_genome', None)
            if dict_to_genome_func and callable(dict_to_genome_func):
                # Assuming dict_to_genome takes a dictionary like {"params": new_params}
                # and returns a Genome object.
                genome_from_dict: Genome = dict_to_genome_func({"params": new_params})
                add_genome_func: Optional[Callable[[Genome], None]] = getattr(genetic_engine, 'add_genome', None)
                if add_genome_func and callable(add_genome_func):
                    add_genome_func(genome_from_dict)
                    note_llm_mutation()
                    logger.debug(f"Node {node_id} added new mutated genome to population.")
                else:
                    logger.error(f"Node {node_id} genetic engine lacks 'add_genome' method. Cannot add new genome.")
            else:
                logger.error(f"Node {node_id} lacks 'dict_to_genome' method to convert new params to genome. Cannot add new genome.")
        else:
            logger.info(f"Node {node_id} LLM mutation resulted in no change from champion parameters.")

    def _genetic_step(self) -> None:
        """
        Executes one genetic evolution step for the node's population.

        This involves evolving a new generation, evaluating the champion,
        applying semantic rules, and potentially publishing the champion's genome
        to the CRDT (with or without gossip signing). If the new champion is superior
        to the node's current parameters, the node's parameters and dispatcher
        are updated. The champion's performance is also added to the node's memory.
        """
        node_id: str = self.node.node_id
        logger.info(f"Node {node_id} performing genetic evolution step.")

        genetic_engine = getattr(self.node, 'engine', None)
        if not (genetic_engine and hasattr(genetic_engine, 'evolve_generation') and callable(genetic_engine.evolve_generation)):
            logger.error(f"Node {node_id} genetic engine lacks 'evolve_generation' method. Skipping genetic step.")
            return

        genetic_engine.evolve_generation()
        logger.debug(f"Node {node_id} evolved a new generation.")

        # Ensure a champion exists and has a positive fitness before proceeding
        # self.node.engine.champion is expected to be a tuple (params: Dict, fitness: float)
        champion: Optional[Tuple[Dict[str, Any], float]] = getattr(genetic_engine, 'champion', None)

        if champion is None or champion[1] <= 0:
            logger.debug(f"Node {node_id} has no champion or non-positive champion fitness ({champion[1] if champion else 'N/A'}). Skipping publish and update.")
            return

        champion_params: Dict[str, Any] = champion[0]
        champion_fitness: float = champion[1]
        logger.debug(f"Node {node_id} identified champion with fitness: {champion_fitness:.4f}")

        node_volatility_func: Optional[Callable[[], float]] = getattr(self.node, '_current_volatility', None)
        current_volatility: float = node_volatility_func() if node_volatility_func else 0.0

        node_survival = getattr(self.node, 'survival', None)
        current_dq: float = getattr(node_survival, 'dq', 0.0) if node_survival else 0.0

        # Apply semantic rules to the champion's parameters before publishing
        params_to_publish: Dict[str, Any]
        semantic_engine = getattr(self.node, 'semantic', None)
        if semantic_engine and hasattr(semantic_engine, 'apply_rules') and callable(semantic_engine.apply_rules):
            params_to_publish = semantic_engine.apply_rules(
                champion_params, current_volatility, current_dq
            )
            logger.debug(f"Node {node_id} applied semantic rules to champion parameters.")
        else:
            logger.warning(f"Node {node_id} lacks 'semantic' object or 'apply_rules' method. Publishing raw champion params.")
            params_to_publish = champion_params

        make_genome_func: Optional[Callable[[Dict[str, Any], float], Dict[str, Any]]] = getattr(self.node, 'make_genome', None)
        if not (make_genome_func and callable(make_genome_func)):
            logger.error(f"Node {node_id} lacks 'make_genome' method. Cannot publish genome.")
            return

        # Assuming make_genome creates a dict suitable for CRDT (e.g., {"params": ..., "fitness": ...})
        genome_dict: Dict[str, Any] = make_genome_func(params_to_publish, champion_fitness)

        if config.gossip_signing_enabled:
            # Ensure necessary attributes for gossip are present
            required_gossip_attrs = [
                'gossip_seq_no', 'gossip_lamport_ts', 'node_id', 'gossip_public_bytes',
                'gossip_key_id', 'gossip_private_key', 'crdt'
            ]
            if not all(hasattr(self.node, attr) for attr in required_gossip_attrs):
                logger.error(f"Node {node_id} missing attributes for gossip signing. Skipping genome publish.")
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
                "sender_pubkey": self.node.gossip_public_bytes, # Expected to be bytes or hex string
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
                # sign_envelope is assumed to take the raw payload (genome_dict) and return a Pydantic-like model
                # The model_dump(mode='json') then converts it for CRDT.
                envelope_signed: GossipEnvelopeModel = sign_envelope(genome_dict, meta, self.node.gossip_private_key)
                crdt_add_genome_func: Optional[Callable[[Dict[str, Any]], Any]] = getattr(self.node.crdt, 'add_genome', None)
                if crdt_add_genome_func and callable(crdt_add_genome_func):
                    # Ensure the add_genome method of CRDT is awaited if it's async
                    asyncio.create_task(crdt_add_genome_func(envelope_signed.model_dump(mode='json')))
                    logger.info(f"Node {node_id} published signed champion genome to CRDT.")
                else:
                    logger.error(f"Node {node_id} CRDT lacks 'add_genome' method. Cannot publish genome.")
            except Exception as e:
                logger.error(f"Failed to sign and publish genome for node {node_id} with gossip: {type(e).__name__}: {e}", exc_info=True)
        else:
            required_unsigned_attrs = ['crypto', 'crdt']
            if not all(hasattr(self.node, attr) for attr in required_unsigned_attrs):
                logger.error(f"Node {node_id} missing crypto or CRDT attributes for unsigned publish. Skipping genome publish.")
                return
            crypto_obj = getattr(self.node, 'crypto')
            if not (hasattr(crypto_obj, 'sign') and callable(crypto_obj.sign) and
                    hasattr(crypto_obj, 'public_bytes_hex') and isinstance(crypto_obj.public_bytes_hex, str)):
                logger.error(f"Node {node_id} crypto object missing 'sign' method or 'public_bytes_hex' attribute. Skipping genome publish.")
                return

            payload_for_sign: Dict[str, Any] = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]}
            genome_dict["signature"] = crypto_obj.sign(payload_for_sign)
            genome_dict["origin_pubkey"] = crypto_obj.public_bytes_hex

            crdt_add_genome_func: Optional[Callable[[Dict[str, Any]], Any]] = getattr(self.node.crdt, 'add_genome', None)
            if crdt_add_genome_func and callable(crdt_add_genome_func):
                asyncio.create_task(crdt_add_genome_func(genome_dict))
                logger.info(f"Node {node_id} published unsigned champion genome to CRDT.")
            else:
                logger.error(f"Node {node_id} CRDT lacks 'add_genome' method. Cannot publish genome.")

        # Update node's current parameters and dispatcher if the champion is better
        current_params_fitness: float = -1.0 # Default if _fitness is not available or current_params is not set
        if hasattr(self.node, 'current_params') and self.node.current_params is not None and \
           genetic_engine and hasattr(genetic_engine, '_fitness') and callable(genetic_engine._fitness):
            current_params_fitness = genetic_engine._fitness(self.node.current_params)

        if champion_fitness > current_params_fitness:
            self.node.current_params = champion_params
            # Assuming ROIDispatcher takes config as a dictionary of parameters
            self.node.dispatcher = ROIDispatcher(config=self.node.current_params)
            logger.info(f"Node {node_id} updated current parameters to new champion (fitness {champion_fitness:.4f}).")
        else:
            logger.debug(f"Node {node_id} champion (fitness={champion_fitness:.4f}) not superior to current params (fitness={current_params_fitness:.4f}). No parameter update.")

        # Add champion's performance to node's memory
        node_memory = getattr(self.node, 'memory', None)
        if node_memory and hasattr(node_memory, 'add') and callable(node_memory.add):
            node_capital_val: float = getattr(self.node, 'capital', 0.0)
            node_niche_val: str = node_niche_func() if node_niche_func else "N/A" # Use the niche for memory
            node_memory.add(
                market_volatility=current_volatility,
                dq=current_dq,
                capital=node_capital_val,
                params=champion_params,
                fitness=champion_fitness,
                niche=node_niche_val # Added niche to memory add
            )
            logger.debug(f"Node {node_id} added champion to memory.")
        else:
            logger.warning(f"Node {node_id} lacks 'memory' object or 'add' method. Cannot add champion to memory.")

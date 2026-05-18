import os, time, random, uuid, hashlib, asyncio, logging, sys, signal, socket
import math
from typing import Dict, Any, Optional, List, Tuple, Callable

import aiohttp

from src.core.global_state import GlobalState
from sim.genetic_engine import GeneticEngine, Genome
from sim.survival_evaluator import SurvivalEvaluator
from sim.curiosity_engine import CuriosityEngine
from sim.meta_pomdp_agent import MetaPOMDPAgent
from src.core.crdt_adapter import CRDTAdapter
from src.core.gossip_adapter import SafeGossipAdapter
from src.security.crypto_manager import CryptoManager
from src.security.reputation_manager import ReputationManager
from src.intelligence.episodic_memory import EpisodicMemory
from src.intelligence.semantic_memory import SemanticMemory
from src.intelligence.llm_client import LLMClient
from src.security.gossip_envelope import sign_envelope, generate_key_pair, sha256
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from src.memory.local_memory import LocalMemoryAPI, MemoryRecord
from src.core.events import Event
from src.core.event_store import EventStore
from src.security.key_manager import KeyManager
from adapters.multi_pair_adapter import MultiPairAdapter
from src.intelligence.internet_researcher import InternetResearcher
from adapters.tradingview_webhook import TradingViewWebhook
from adapters.orderbook_analyzer import OrderBookAnalyzer
from src.observability.telegram_notifier import TelegramNotifier
from swarm_config import config
from src.core.trading_controller import TradingController
from src.evolution.mutation_engine import MutationEngine
from src.economy.roi_dispatcher import ROIDispatcher
from mvp.lab_swarm_demo.leader import select_leader
from mvp.lab_swarm_demo.execution import build_backend
from mvp.lab_swarm_demo.market import MarketSnapshotService, select_best_market
from mvp.lab_swarm_demo.capital_manager import CapitalManager
from mvp.lab_swarm_demo.telemetry import Telemetry
from mvp.lab_swarm_demo.evolution import EvolutionEngine
from mvp.lab_swarm_demo.swarm_sync import SwarmSync
from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation, update_llm_impact, get_llm_stats, _llm_mutation_count

logger = logging.getLogger("SwarmNode")
trade_logger = logging.getLogger("SwarmNode.Trade")
logging.basicConfig(level=config.log_level)

EXPECTED_RETURN_RATE: float = config.expected_return_rate
MAX_NORMALIZED_CAPITAL: float = config.max_normalized_capital


class SwarmNode:
    """
    Represents a single node in the trading swarm, responsible for executing trades,
    participating in evolution, and syncing state with other nodes.

    It integrates various components including CRDT for state synchronization,
    a genetic engine for strategy evolution, an LLM for mutations, and a capital manager
    for survival.
    """
    def __init__(self) -> None:
        """
        Initializes the SwarmNode with its configuration and various integrated components.
        """
        # Node Configuration
        self.node_id: str = config.NODE_ID
        self.port: int = config.PORT
        self.peers: List[str] = config.PEERS

        self.node_index: int = abs(hash(socket.gethostname())) % config.total_nodes
        logger.info(f"Node index: {self.node_index}/{config.total_nodes}")

        self.gossip_seq_no: int = 0
        self.gossip_lamport_ts: int = 0

        # Gossip signing keys
        self.gossip_private_key: Ed25519PrivateKey = Ed25519PrivateKey.generate()
        self.gossip_public_bytes: bytes = self.gossip_private_key.public_key().public_bytes_raw()
        self.gossip_key_id: str = hashlib.sha256(self.gossip_public_bytes).hexdigest()[:16]

        self.market_url: Optional[str] = config.MARKET_URL
        self.market_mode: str = config.market_mode

        self.burn_rate: float = config.BURN_RATE
        self.failure_prob: float = config.FAILURE_PROB
        self.gossip_interval: float = config.GOSSIP_INTERVAL
        self.max_state: int = config.MAX_STATE
        self.ttl: int = config.TTL
        self.max_import: int = config.MAX_IMPORT
        self.import_cooldown: int = config.IMPORT_COOLDOWN

        self.swarm_sync: SwarmSync = SwarmSync(self)

        # ========== INFRASTRUCTURE LAYER (BODY) ==========
        self.key_manager: KeyManager = KeyManager()
        self.crypto: CryptoManager = CryptoManager()

        self.reputation: ReputationManager = ReputationManager()
        self.reputation_blacklist_threshold: float = 0.3

        self.memory_api_enabled: bool = config.memory_api_enabled
        self.memory_api: LocalMemoryAPI = LocalMemoryAPI(
            node_id=self.node_id,
            storage=None # Storage is set later, after CRDT is initialized
        )

        self.internet_researcher: InternetResearcher = InternetResearcher(
            memory_api=self.memory_api if self.memory_api_enabled else None
        )
        self.telegram_notifier: TelegramNotifier = TelegramNotifier()

        self.crdt: CRDTAdapter = CRDTAdapter(
            node_id=self.node_id,
            memory_api=self.memory_api if self.memory_api_enabled else None,
            reputation=self.reputation,
            db_path=config.crdt_db_path
        )

        if self.memory_api_enabled:
            # Now CRDT is initialized, assign its storage to memory_api
            self.memory_api.storage = self.crdt.storage

        self.gossip: SafeGossipAdapter = SafeGossipAdapter(self.crdt)
        self.gossip.set_reputation_manager(self.reputation)

        self.event_store: EventStore = EventStore(
            ledger_path=config.event_ledger_path,
            sqlite_path=config.event_sqlite_path,
        )

        self.telemetry: Telemetry = Telemetry(
            node_id=self.node_id,
            event_store=self.event_store,
            telegram_notifier=self.telegram_notifier,
            get_llm_stats_func=get_llm_stats,
            update_llm_impact_func=update_llm_impact,
        )

        trading_symbols: str = config.trading_symbols
        symbols_list: List[str] = [s.strip() for s in trading_symbols.split(",") if s.strip()]
        self.symbols_list: List[str] = symbols_list
        self.market_adapter: MultiPairAdapter = MultiPairAdapter(
            symbols=symbols_list,
            market_mode=self.market_mode,
            crdt_adapter=self.crdt if self.market_mode == "web3" else None
        )
        self.market_service: MarketSnapshotService = MarketSnapshotService(
            market_adapter=self.market_adapter,
            market_mode=self.market_mode,
        )

        if self.market_mode == "web3":
            for sym in symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                # Ensure the web3 adapter also has access to the CRDT
                if adapter and hasattr(adapter, 'crdt'):
                    adapter.crdt = self.crdt

        self.primary_symbol: str = symbols_list[0] if symbols_list else "BTC/USDT"

        self.tradingview_enabled: bool = config.tradingview_webhook_enabled
        self.tradingview_webhook: Optional[TradingViewWebhook] = None
        if self.tradingview_enabled:
            self.tradingview_webhook = TradingViewWebhook(port=config.tradingview_webhook_port)

        self.orderbook_enabled: bool = config.orderbook_analysis_enabled
        self.orderbook_analyzers: Dict[str, OrderBookAnalyzer] = {}
        if self.orderbook_enabled:
            for sym in symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter:
                    self.orderbook_analyzers[sym] = OrderBookAnalyzer(adapter)

        # ========== INTELLIGENCE LAYER (BRAIN) ==========
        self.engine: GeneticEngine = GeneticEngine(pop_size=10)
        self.engine.initialize()

        self.state: GlobalState = GlobalState()
        best: Dict[str, Dict[str, float]] = self.state.get_best_genomes(top_n=1)
        # Initialize with default params if no best genome is found
        self.current_params: Dict[str, float] = list(best.values())[0] if best else {"max_risk_per_trade": 0.05, "phi_llm": 0.15, "stop_loss_ratio": 0.05, "trailing_stop_ratio": 0.01, "momentum_window": 10, "volatility_threshold": 0.02}
        self.dispatcher: ROIDispatcher = ROIDispatcher(config=self.current_params)

        self.survival: SurvivalEvaluator = SurvivalEvaluator()
        self.survival.dq = 0.03
        self.survival.liveness = 1.0

        self.curiosity: CuriosityEngine = CuriosityEngine(window_size=10, surprise_threshold=0.3)
        self.meta_agent: MetaPOMDPAgent = MetaPOMDPAgent() # This seems unused, consider removal if truly not used.
        self.llm: LLMClient = LLMClient()

        self.memory: EpisodicMemory = EpisodicMemory(max_size=500)
        self.semantic: SemanticMemory = SemanticMemory()

        # ========== RUNTIME STATE ==========
        self.capital: float = 1000.0
        self.step_count: int = 0
        self.last_import_step: int = 0
        self._prev_price: float = 100.0
        self._prev_prev_price: float = 100.0
        self._last_market: Optional[Dict[str, Any]] = None
        self._trace_id: str = "" # Initialize trace_id for event tracing

        self._seed_from_memory()

        self.trading_controller: TradingController = TradingController(self.node_id)
        self.nonce_manager: Any = None # Placeholder, will be set for web3 mode
        self.mutation_engine: MutationEngine = MutationEngine(self.llm, node_id=self.node_id, nonce_manager=self.nonce_manager, event_store=self.event_store)

        self.evolution_engine: EvolutionEngine = EvolutionEngine(self)

        self.capital_manager: CapitalManager = CapitalManager(capital=self.capital)
        self.capital_manager.set_survival(self.survival)

        # Initialize executor with a placeholder adapter; it will be updated in start() for web3.
        self.executor: Any = build_backend(
            node_id=self.node_id,
            adapter=None, # Placeholder
            is_leader_func=self.is_leader,
        )

        # Background tasks handles
        self._evolution_task: Optional[asyncio.Task[Any]] = None
        self._sync_task: Optional[asyncio.Task[Any]] = None

    def is_leader(self, block_number: int) -> bool:
        """
        Determines if this node is the leader for a given block number.

        Args:
            block_number: The current block number (used for leader selection).

        Returns:
            True if this node is the leader, False otherwise.
        """
        leader_index: int = select_leader(self.node_id, block_number, config.total_nodes)
        return self.node_index == leader_index
    
    async def _apply_meta_commands(self) -> None:
        """
        Applies meta-commands received from the CRDT state, adjusting node parameters.
        These commands are issued by the MetaAgent to influence swarm behavior.
        """
        try:
            all_state: Dict[str, Any] = self.crdt.state
            json_commands: List[Dict[str, Any]] = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "meta_command_json"]
            
            now: float = time.time()
            json_commands = [c for c in json_commands if float(c.get("expires_at", now + 1)) > now]

            if json_commands:
                # Get the latest command based on timestamp
                latest_json: Dict[str, Any] = max(json_commands, key=lambda x: float(x.get("timestamp", 0)))
                data: Dict[str, Any] = latest_json.get("data", {})
                
                if data.get("action") == "ADJUST_SWARM":
                    params: Dict[str, Any] = data.get("params", {})
                    alpha: float = 0.1 # Smoothing factor for adjustments

                    if "risk_scale" in params:
                        raw_risk_scale: float = float(params["risk_scale"])
                        # Apply a tanh function to scale raw_risk_scale around 1.0 (neutral)
                        adjustment: float = alpha * math.tanh(raw_risk_scale - 1.0)
                        old_risk: float = self.current_params.get("max_risk_per_trade", 0.05)
                        new_risk: float = old_risk * (1 + adjustment)
                        new_risk = max(0.005, min(0.15, new_risk)) # Keep risk within reasonable bounds
                        self.current_params["max_risk_per_trade"] = new_risk
                        logger.info(f"🧠 MetaAgent JSON: risk {old_risk:.4f} → {new_risk:.4f}")

                    if "exploration_multiplier" in params:
                        mult: float = float(params["exploration_multiplier"])
                        old_rate: float = getattr(self.engine, '_mutation_rate', 0.25)
                        new_rate: float = max(0.1, min(0.7, old_rate * mult)) # Keep exploration rate bounded
                        if hasattr(self.engine, 'set_mutation_rate'):
                            self.engine.set_mutation_rate(new_rate)
                        logger.info(f"🧠 MetaAgent JSON: exploration rate → {new_rate:.2f}")

                    if "survival_bias_adj" in params:
                        delta: float = max(-0.05, min(0.05, float(params["survival_bias_adj"]))) # Clamp adjustment delta
                        old_sb: float = self.survival.config.get("lambda", 0.15)
                        new_sb: float = max(0.1, min(0.9, old_sb + delta)) # Keep survival bias bounded
                        self.survival.config["lambda"] = new_sb
                        logger.info(f"🧠 MetaAgent JSON: survival lambda → {new_sb:.3f}")

                    if "stop_loss_adj" in params:
                        factor: float = float(params["stop_loss_adj"])
                        old_sl: float = self.current_params.get("stop_loss_ratio", 0.05)
                        new_sl: float = max(0.001, min(0.2, old_sl * factor)) # Keep stop loss ratio bounded
                        self.current_params["stop_loss_ratio"] = new_sl
                        logger.info(f"🧠 MetaAgent JSON: stop-loss {old_sl:.4f} → {new_sl:.4f}")

        except Exception as e:
            logger.debug(f"Meta command processing skipped: {e}", exc_info=True) # Added exc_info for better debugging

    async def _evolution_cycle(self) -> None:
        """Background loop for the evolution engine (genetics, LLM mutations)."""
        while True:
            try:
                await self._tick_evolution()
            except Exception as e:
                logger.error(f"Evolution cycle error: {e}", exc_info=True)
            await asyncio.sleep(0.5)

    async def _sync_cycle(self) -> None:
        """Background loop for swarm synchronization (gossip, genome import)."""
        while True:
            try:
                await self._sync_swarm()
            except Exception as e:
                logger.error(f"Sync cycle error: {e}", exc_info=True)
            await asyncio.sleep(0.5)

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def node_niche(self) -> str:
        """
        Determines the current operational niche of the node based on its survival
        quotient and capital.

        Returns:
            A string indicating the node's current niche ("survival", "capital", "exploration").
        """
        if self.survival.dq >= 0.8 or self.survival.liveness < 0.5:
            return "survival"
        if self.capital > 50000 and self.survival.dq < 0.3:
            return "capital"
        return "exploration"

    def accept_genome(self, genome: Dict[str, Any]) -> bool:
        """
        Checks if a given genome should be accepted into the node's population.

        Args:
            genome: A dictionary representing the genome.

        Returns:
            True if the genome meets acceptance criteria, False otherwise.
        """
        if float(genome.get("fitness", 0)) < 0.001:
            return False
        # Ensure parameters are within a reasonable range (0, 10)
        for v in genome.get("params", {}).values():
            if not (0 < float(v) < 10):
                return False
        pubkey_hex: Optional[str] = genome.get("origin_pubkey_hex") # Assuming hex representation
        if pubkey_hex:
            # Convert hex string back to bytes for reputation manager
            try:
                pubkey_bytes = bytes.fromhex(pubkey_hex)
                if not self.reputation.is_trusted(pubkey_bytes):
                    return False
            except ValueError:
                logger.debug(f"Invalid pubkey_hex encountered: {pubkey_hex}")
                return False
        return True

    def make_genome(self, params: Dict[str, float], fitness: float) -> Dict[str, Any]:
        """
        Creates a new genome dictionary with specified parameters and fitness.

        Args:
            params: A dictionary of parameters for the genome.
            fitness: The fitness score of the genome.

        Returns:
            A dictionary representing the new genome.
        """
        return {
            "params": params,
            "fitness": fitness,
            "niche": self.node_niche(),
            "origin": self.node_id,
            "lineage": [self.node_id],
            "ts": time.time(),
            "origin_pubkey_hex": self.crypto.public_bytes_hex, # Store public key in hex
        }

    def dict_to_genome(self, d: Dict[str, Any], niche: str = "exploration") -> Genome:
        """
        Converts a dictionary representation into a Genome object.

        Args:
            d: A dictionary containing genome data.
            niche: The default niche if not specified in the dictionary.

        Returns:
            A Genome object.
        """
        # Ensure that params are floats and lineage is a list of strings
        genome_params: Dict[str, float] = {str(k): float(v) for k, v in d.get("params", d).items() if isinstance(v, (int, float))}
        genome_fitness: float = float(d.get("fitness", 0.0))
        genome_niche: str = str(d.get("niche", niche))
        
        raw_lineage = d.get("lineage", [])
        if not isinstance(raw_lineage, list):
            raw_lineage = []
        
        # Ensure lineage items are strings, and limit length
        genome_lineage: List[str] = [str(item) for item in raw_lineage[-5:]] + [self.node_id]
        
        return Genome(
            params=genome_params,
            fitness=genome_fitness,
            niche=genome_niche,
            lineage=genome_lineage,
        )

    def local_score(self, genome: Genome) -> float:
        """
        Calculates a local score for a genome, biasing based on node's niche and memory.

        Args:
            genome: The Genome object to score.

        Returns:
            The calculated local score.
        """
        base: float = genome.fitness
        bias: float = 1.0
        if genome.niche == "survival":
            bias += min(0.5, self.survival.liveness)
        elif genome.niche == "exploration":
            bias += min(0.3, self.curiosity.surprise_threshold)
        elif genome.niche == "capital":
            bias += min(0.5, self.capital / 2000.0) # Ensure float division

        if len(self.memory) > 0:
            vol: float = self._current_volatility()
            # Assuming MemoryRecord has compatible types for find_similar
            similar: List[MemoryRecord] = self.memory.find_similar(vol, self.survival.dq, top_k=5)
            for rec in similar:
                # Compare params by value, not by object identity
                if rec.get("params") == genome.params:
                    bias += 0.2
                    break
        return base * bias

    def population_diversity(self) -> float:
        """
        Calculates the diversity of the current genetic population.
        Diversity is measured by the ratio of unique genome parameter sets to the total population size.

        Returns:
            A float representing the population diversity (0.0 to 1.0).
        """
        pop: List[Genome] = self.engine.population
        if not pop:
            return 0.0
        
        # Use a frozen set of items to ensure dictionary key uniqueness for comparison
        # This handles cases where dict order might change but content is the same
        sigs = {frozenset(g.params.items()) for g in pop if isinstance(g, Genome)}
        return len(sigs) / len(pop)

    def population_niche_counts(self) -> Dict[str, int]:
        """
        Counts the number of genomes belonging to each niche in the population.

        Returns:
            A dictionary where keys are niche names and values are their counts.
        """
        counts: Dict[str, int] = {"survival": 0, "capital": 0, "exploration": 0}
        for g in self.engine.population:
            niche: str
            if isinstance(g, Genome):
                niche = g.niche
            elif isinstance(g, dict):
                niche = g.get("niche", "exploration")
            else:
                continue # Skip if not a recognizable genome type
            counts[niche] = counts.get(niche, 0) + 1
        return counts

    def _current_volatility(self) -> float:
        """
        Calculates the current market volatility based on previous prices.

        Returns:
            The calculated volatility.
        """
        # Ensure these are float values, use getattr with defaults
        prev: float = getattr(self, '_prev_price', 100.0)
        prev_prev: float = getattr(self, '_prev_prev_price', 100.0)
        
        # Avoid division by zero
        denominator = max(1.0, prev_prev)
        return abs(prev - prev_prev) / denominator

    def _seed_from_memory(self) -> None:
        """
        Seeds the genetic engine's population with relevant genomes from memory.
        It looks for past trading parameters that performed well under similar market conditions.
        """
        if not self.memory.records:
            return
        current_volatility: float = self._current_volatility()
        # Find similar records based on volatility and survival quotient
        similar: List[MemoryRecord] = self.memory.find_similar(current_volatility, self.survival.dq, top_k=3)
        for rec in similar:
            try:
                # Assuming 'params' in MemoryRecord is a Dict[str, float]
                genome: Genome = self.dict_to_genome({"params": rec["params"]})
                self.engine.add_genome(genome)
            except Exception as e:
                logger.debug(f"Seed from memory skipped for record {rec}: {e}")

    # ------------------------------------------------------------
    # Market
    # ------------------------------------------------------------
    async def get_market_tick(self, session: aiohttp.ClientSession, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        """
        Fetches the current market tick for a given symbol from the market adapter
        or a fallback market URL.

        Args:
            session: An aiohttp client session for making HTTP requests.
            symbol: The trading symbol to fetch (e.g., "BTC/USDT").

        Returns:
            A dictionary containing market data (at least a "price" key).
        """
        if self.market_mode == "live" and self.market_adapter:
            adapter = self.market_adapter.get_adapter(symbol)
            if adapter:
                tick: Optional[Dict[str, Any]] = await adapter.get_ticker()
                if tick is not None:
                    scale: float = config.trading.price_scale
                    # Ensure 'price' key exists, defaulting to 'ask' or 50000 if neither
                    tick['price'] = float(tick.get('price', tick.get('ask', 50000)))
                    tick['price'] = tick['price'] / scale
                    return tick
        
        if self.market_url:
            try:
                async with session.get(self.market_url, timeout=1) as resp:
                    resp.raise_for_status() # Raise an exception for bad status codes
                    return await resp.json()
            except Exception as e:
                logger.debug(f"Market URL request failed: {e}")
        
        # Fallback if no market data is obtained
        return {"price": random.uniform(90, 110)}

    # ------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------
    async def main_loop(self) -> None:
        """
        The main operational loop of the SwarmNode, handling market interactions,
        survival evaluation, trading, and periodic tasks.
        """
        async with aiohttp.ClientSession() as session:
            if self.memory_api_enabled:
                await self.memory_api.load_from_db()

            while True:
                self.step_count += 1
                self._trace_id = str(uuid.uuid4())

                if self.failure_prob > 0 and random.random() < self.failure_prob:
                    await self.telemetry.spore_failure(
                        step=self.step_count,
                        capital=self.capital,
                        dq=self.survival.dq,
                        fitness=self.engine.champion[1] if self.engine.champion else 0.0,
                        diversity=self.engine.diversity(),
                        crdt_size=len(self.crdt.state),
                        trace_id=self._trace_id,
                    )
                    logger.info(f"[{self.node_id}] failed and exiting.")
                    # Use sys.exit() or raise SystemExit here to gracefully stop the loop and tasks.
                    sys.exit(1)

                # 1. Market data collection
                best_symbol, best_market, snapshot = await self._collect_market_snapshot(session)

                # Update prices for volatility calculation
                self._prev_prev_price = self._prev_price
                self._prev_price = float(best_market.get("price", 100.0))

                # 2. Auto-conversion and Stop-loss logic
                if self.market_mode == "web3":
                    adapter = self.market_adapter.get_adapter(best_symbol)
                    if adapter and hasattr(adapter, 'w3'): # Check if web3 adapter and has w3 attribute
                        try:
                            block_number: int = await adapter.w3.eth.block_number
                            if self.is_leader(block_number):
                                await self.trading_controller.check_and_rebalance(adapter)
                        except Exception as e:
                            logger.warning(f"Web3 rebalance check failed: {e}")

                if self.market_mode == "futures":
                    adapter = self.market_adapter.get_adapter(best_symbol)
                    if adapter and hasattr(adapter, 'exchange') and hasattr(adapter, 'check_stop_loss'):
                        try:
                            positions: List[Dict[str, Any]] = await adapter.exchange.fetch_positions([best_symbol])
                            if positions:
                                pos: Dict[str, Any] = positions[0] # Assuming one position per symbol
                                contracts = float(pos.get('contracts', 0.0))
                                if contracts != 0.0:
                                    entry_price: float = float(pos.get('entryPrice', 0.0))
                                    current_price: float = float(best_market['price'])
                                    side: str = 'long' if contracts > 0 else 'short'
                                    if adapter.check_stop_loss(entry_price, current_price, side):
                                        logger.info(f"Stop-loss triggered for {best_symbol}")
                                        await adapter.close_position(best_symbol)
                                        await self.telegram_notifier.send(
                                            f"🛑 <b>Stop-loss triggered</b>\n"
                                            f"Node: {self.node_id}\n"
                                            f"Symbol: {best_symbol}\n"
                                            f"Capital: {self.capital:.2f}"
                                        )
                                        if self.market_adapter.hedge_enabled:
                                            spot_adapter = self.market_adapter.get_adapter(best_symbol, "spot")
                                            if spot_adapter:
                                                try:
                                                    await spot_adapter.close_position(best_symbol)
                                                except Exception as e:
                                                    logger.warning(f"Hedge close failed: {e}")
                        except Exception as e:
                            logger.warning(f"Futures stop-loss check failed: {e}", exc_info=True)

                # 3. Capital Burn
                self.capital_manager.burn()
                self.capital = self.capital_manager.capital
                if not self.capital_manager.is_alive():
                    logger.info(f"[{self.node_id}] died due to insufficient capital. Exiting.")
                    sys.exit(0)

                # 4. Survival Evaluation + Trade Execution
                await self._evaluate_survival_and_trade(best_market, best_symbol)

                self._last_market = best_market

                # 7. Periodic tasks (e.g., heartbeats, CRDT pruning, meta command application)
                await self._periodic_tasks()

                # 8. Low capital alert
                self.telemetry.update_impact(self.capital)
                alert_threshold: float = config.capital_alert_threshold
                if self.capital < alert_threshold:
                    await self.telemetry.low_capital_alert(self.capital, alert_threshold)

                await asyncio.sleep(0.5)

    def _recombine(self, g1: Dict[str, Any], g2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recombines two parent genomes to produce a child genome.

        Args:
            g1: The first parent genome (dictionary).
            g2: The second parent genome (dictionary).

        Returns:
            A new dictionary representing the child genome.
        """
        all_keys: set = set(g1.get("params", {}).keys()) | set(g2.get("params", {}).keys())
        child_params: Dict[str, float] = {}
        for k in all_keys:
            v1: float = float(g1.get("params", {}).get(k, 0.5))
            v2: float = float(g2.get("params", {}).get(k, 0.5))
            val: float = v1 if random.random() < 0.5 else v2 # Randomly pick from parent
            if random.random() < 0.1: # Small mutation chance
                val *= random.uniform(0.9, 1.1)
            val = max(0.0001, min(10.0, val)) # Clamping the value to a reasonable range
            child_params[k] = val
        
        # Determine child niche based on parents or a random choice
        child_niche: str = g1.get("niche", "mixed") if random.random() < 0.5 else g2.get("niche", "mixed")
        
        # Create lineage
        lineage1 = [str(item) for item in g1.get("lineage", [])[-5:]]
        lineage2 = [str(item) for item in g2.get("lineage", [])[-5:]]
        child_lineage: List[str] = (lineage1 if random.random() < 0.5 else lineage2) + [self.node_id]

        return {
            "params": child_params,
            "fitness": 0.0, # Child's fitness needs to be evaluated later
            "niche": child_niche,
            "origin": self.node_id,
            "lineage": child_lineage,
            "ts": time.time(),
            "origin_pubkey_hex": self.crypto.public_bytes_hex,
        }

    async def _collect_market_snapshot(self, session: aiohttp.ClientSession) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """
        Collects a market snapshot for all configured symbols and selects the best market for trading.

        Args:
            session: An aiohttp client session.

        Returns:
            A tuple containing:
                - The symbol of the best market (str).
                - The market data of the best market (Dict[str, Any]).
                - The complete market snapshot (Dict[str, Any]).
        """
        snapshot: Dict[str, Any] = await self.market_service.get_snapshot(session)
        best_symbol: str
        best_market: Dict[str, Any]
        best_symbol, best_market = select_best_market(snapshot)
        return best_symbol, best_market, snapshot

    async def _evaluate_survival_and_trade(self, market: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        """
        Evaluates trading opportunities based on survival criteria and executes trades.

        Args:
            market: Dictionary containing current market data (e.g., price).
            symbol: The trading symbol.

        Returns:
            The result of the trade execution (dictionary) if a trade occurred, otherwise None.
        """
        market_price = float(market.get("price", 0.0))
        if market_price == 0.0:
            logger.warning(f"Market price is 0 for {symbol}, skipping trade evaluation.")
            return None

        expected_return_amount: float = market_price * EXPECTED_RETURN_RATE
        _, approved = self.survival.evaluate_trade(self.capital, expected_return_amount)
        logger.info(f"[{self.node_id}] Survival approved={approved}, capital={self.capital:.2f}, expected={expected_return_amount:.4f}")
        if not approved:
            return None

        fraction, _ = self.dispatcher.evaluate(market, self.capital)
        if fraction <= 0:
            return None

        # Determine trade side and amount based on configuration and dispatcher output
        side: str = config.trading.test_web3_swap_side # Default or config-driven
        test_amount: float = config.trading.test_web3_swap_amount # Default or config-driven

        # If fraction is dynamic, convert it to an actual trade amount
        # This assumes test_amount is a base, and fraction scales it
        trade_amount = test_amount * fraction 
        if trade_amount <= 0:
             return None

        prev_capital: float = self.capital
        trade_result: Optional[Dict[str, Any]] = None

        try:
            trade_result = await self.executor.execute_order(
                symbol=symbol,
                side=side,
                amount=trade_amount,
                price=market_price,
                capital=self.capital,
            )
        except Exception as e:
            logger.error(f"Trade execution failed for {symbol} ({side} {trade_amount}): {e}", exc_info=True)
            trade_result = {"success": False, "status": f"failed: {e}"}

        # Simulate return and capital burn (even if trade failed, burn can occur)
        # Note: The original code applied a return here even if trade_result was None or failed.
        # This might be intended as a general "market activity" simulation, not tied to specific trade success.
        # To strictly tie return/burn to trade success, move this block inside `if trade_result and trade_result.get("success")`.
        # Assuming the original intent was broader market interaction.
        ret: float = market_price * fraction * 0.1 # This calculation might need adjustment based on trade_amount.
        self.capital *= (1 + ret)
        self.capital -= config.trading.transaction_cost # Simulate transaction cost from config
        self.capital_manager.capital = self.capital
        self.capital_manager.apply_dq_delta(0.001)

        if trade_result and trade_result.get("success"):
            trade_logger.info(f"TRADE | {symbol} | {side} | status: {trade_result.get('status')} | amount: {trade_amount:.4f}")
            self.telemetry.update_impact(self.capital)

        # Hedge logic for futures
        if self.market_mode == "futures" and self.market_adapter.hedge_enabled:
            hedge_ratio: float = config.hedge_ratio
            spot_adapter = self.market_adapter.get_adapter(symbol, "spot")
            futures_adapter = self.market_adapter.get_adapter(symbol, "futures")
            if spot_adapter and futures_adapter:
                # Hedge side is opposite to the futures trade side
                side_hedge: str = 'sell' if side == 'buy' else 'buy'
                hedge_amount: float = abs(trade_amount) * hedge_ratio # Calculate hedge amount based on futures trade
                
                if hedge_amount > 0:
                    try:
                        await spot_adapter.place_order(side_hedge, hedge_amount)
                        logger.info(f"Hedge order placed: {side_hedge} {hedge_amount} {symbol}")
                    except Exception as e:
                        logger.error(f"Hedge order failed for {symbol}: {e}", exc_info=True)

        if trade_result and isinstance(trade_result, dict):
            await self.telemetry.trade(
                step=self.step_count,
                symbol=symbol,
                side=side,
                amount=trade_amount, # Use the calculated trade_amount
                tx_hash=trade_result.get("tx_hash", ""),
                status=trade_result.get("status", "unknown"),
                capital_before=prev_capital,
                capital_after=self.capital,
                trace_id=self._trace_id,
            )

        return trade_result

    async def _tick_evolution(self) -> None:
        """
        Executes a single step of the evolution engine.
        """
        if self._last_market: # Ensure market data is available for evolution
            await self.evolution_engine.tick(self._last_market)
        else:
            logger.debug("Skipping evolution tick: _last_market not available.")

    async def _sync_swarm(self) -> None:
        """
        Executes a single step of swarm synchronization.
        """
        await self.swarm_sync.reconcile()

    async def _periodic_tasks(self) -> None:
        """
        Performs periodic maintenance and monitoring tasks for the node,
        including capital watchdog, meta-command application, heartbeats,
        memory management, and CRDT pruning.
        """
        # Watchdog: protection against capital decrease
        if self.capital < config.capital_watchdog_threshold:
            logger.warning(f"[{self.node_id}] Watchdog: low capital ({self.capital:.2f}), gradual rollback of parameters")
            # Define a standard set of parameters for rollback
            std_params: Dict[str, float] = {
                "max_risk_per_trade": 0.05,
                "phi_llm": 0.15,
                "stop_loss_ratio": 0.02,
                "trailing_stop_ratio": 0.01,
                "momentum_window": 10.0, # Ensure float
                "volatility_threshold": 0.02,
            }
            # Gradually roll back current parameters towards standard values
            for k, std_val in std_params.items():
                current_val = self.current_params.get(k, std_val)
                self.current_params[k] = current_val * 0.8 + std_val * 0.2
            self.capital_manager.apply_dq_delta(-0.05) # Penalize DQ

        # Apply meta commands every 50 steps
        if self.step_count % 50 == 0:
            await self._apply_meta_commands()

        # Send heartbeat every 30 steps
        if self.step_count % 30 == 0:
            try:
                current_fitness: float = 0.0
                if self.engine.champion:
                    # Ensure champion[1] (fitness) is a float
                    current_fitness = float(self.engine.champion[1])

                current_diversity: float = self.population_diversity()
                current_crdt_size: int = len(self.crdt.state)
                current_niche_counts: Dict[str, int] = self.population_niche_counts()

                self.telemetry.heartbeat(
                    step=self.step_count,
                    capital=self.capital,
                    dq=self.survival.dq,
                    fitness=current_fitness,
                    diversity=current_diversity,
                    crdt_size=current_crdt_size,
                    llm_mutations=_llm_mutation_count,
                    niche_counts=current_niche_counts,
                    trace_id=self._trace_id,
                )

                # Duplicate heartbeat to CRDT for MetaAgent
                heartbeat_payload: Dict[str, Any] = {
                    "type": "heartbeat",
                    "capital": self.capital,
                    "dq": self.survival.dq,
                    "fitness": current_fitness,
                    "diversity": current_diversity,
                    "crdt_size": current_crdt_size,
                    "llm_mutations": _llm_mutation_count,
                    "niche_counts": current_niche_counts,
                    "node_id": self.node_id,
                    "timestamp": time.time(),
                    "trace_id": self._trace_id,
                    "origin_pubkey_hex": self.crypto.public_bytes_hex,
                }
                await self.crdt.add_genome(heartbeat_payload)
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}", exc_info=True)

        # Memory management and CRDT pruning every 500 steps
        if self.step_count % 500 == 0:
            # Deduplicate records by their parameters, keeping the last one for recency.
            # Convert dict.items() to frozenset for hashability
            deduplicated_records: Dict[frozenset[Tuple[str, Any]], MemoryRecord] = {
                frozenset(rec["params"].items()): rec for rec in self.memory.records
            }
            self.memory.records = list(deduplicated_records.values())

            if len(self.memory.records) > self.memory.max_size:
                # If still over max_size after deduplication, truncate from oldest
                self.memory.records = self.memory.records[-self.memory.max_size:]

            if self.memory_api_enabled:
                await self.memory_api.save_to_db()
                self.event_store.append(Event.create(
                    node_id=self.node_id,
                    event_type="memory_snapshot_created",
                    payload={
                        "step": self.step_count,
                        "records_count": len(self.memory_api._records),
                        "trace_id": self._trace_id,
                    },
                    parent_id=self._trace_id,
                ))

        # Semantic memory derivation and CRDT deep pruning every 200 steps
        if self.step_count % 200 == 0:
            self.semantic.derive_rules(self.memory.to_dict_list())
            await self.crdt.prune() # General CRDT pruning
            await self.crdt.prune_heartbeats(max_age_seconds=600) # Prune old heartbeats

            top_genomes: List[Dict[str, Any]] = await self.crdt.get_top(20)
            if top_genomes:
                sample: Dict[str, Any] = random.choice(top_genomes)
                pubkey_hex: Optional[str] = sample.get("origin_pubkey_hex")
                
                # Compare origin_pubkey_hex with current node's public key hex
                if pubkey_hex and pubkey_hex != self.crypto.public_bytes_hex:
                    try:
                        actual_fit: float = self.engine._fitness(sample["params"])
                        claimed_fit: float = float(sample.get("fitness", 0.0))
                        
                        # Convert hex string back to bytes for reputation manager
                        pubkey_bytes = bytes.fromhex(pubkey_hex)
                        self.reputation.update(pubkey_bytes, claimed_fit, actual_fit)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Reputation update skipped due to invalid data in genome {sample.get('gid', 'N/A')}: {e}")

            if self.memory_api_enabled:
                stats: Dict[str, Any] = await self.memory_api.compress()
                logger.info(f"Memory compression stats: {stats}")

    async def start(self) -> None:
        """
        Initializes and starts the SwarmNode's operations, including network listeners
        and background tasks. This is the main entry point for running the node.
        """
        logger.info(f"[{self.node_id}] starting on port={self.port}, peers={self.peers}")

        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        shutdown_event: asyncio.Event = asyncio.Event()

        if self.tradingview_enabled and self.tradingview_webhook:
            await self.tradingview_webhook.start()

        def _shutdown_handler(*args: Any) -> None:
            logger.info(f"[{self.node_id}] received signal {args[0]}, shutting down gracefully")
            shutdown_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _shutdown_handler)
            except NotImplementedError:
                logger.warning(f"Signal handler for {sig.name} not available on this platform.")

        async def _shutdown_waiter() -> None:
            await shutdown_event.wait()
            logger.info(f"[{self.node_id}] Shutdown signal received, initiating cleanup.")
            
            # Cancel background tasks
            if self._evolution_task:
                self._evolution_task.cancel()
                try:
                    await self._evolution_task
                except asyncio.CancelledError:
                    logger.debug("Evolution task cancelled.")
            if self._sync_task:
                self._sync_task.cancel()
                try:
                    await self._sync_task
                except asyncio.CancelledError:
                    logger.debug("Sync task cancelled.")

            if self.memory_api_enabled:
                await self.memory_api.save_to_db()
                logger.info(f"[{self.node_id}] memory saved before exit")
            if self.tradingview_enabled and self.tradingview_webhook:
                await self.tradingview_webhook.stop()
                logger.info(f"[{self.node_id}] TradingView webhook stopped.")
            
            # Explicitly close CRDT resources if it has a close method
            if hasattr(self.crdt, 'close') and callable(self.crdt.close):
                await self.crdt.close()
                logger.info(f"[{self.node_id}] CRDT resources closed.")

            # Exit the program
            raise SystemExit(0)

        if self.market_mode == "web3":
            # For web3 mode, initialize specific adapters and executor after node's own setup
            first_adapter_for_executor: Optional[Any] = None
            for sym in self.symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter:
                    if hasattr(adapter, 'initialize') and callable(adapter.initialize):
                        logger.info(f"Initializing web3 adapter for {sym} ...")
                        await adapter.initialize()
                    if self.nonce_manager is None and hasattr(adapter, 'nonce_manager'):
                        self.nonce_manager = adapter.nonce_manager
                        self.mutation_engine.nonce_manager = self.nonce_manager
                    if first_adapter_for_executor is None:
                        first_adapter_for_executor = adapter
            
            # Update executor with the initialized adapter for web3
            self.executor = build_backend(self.node_id, first_adapter_for_executor, self.is_leader)

        # Start background tasks
        self._evolution_task = asyncio.create_task(self._evolution_cycle())
        self._sync_task = asyncio.create_task(self._sync_cycle())

        # Gather all main coroutines to run concurrently
        await asyncio.gather(
            self.gossip.start(),
            self.main_loop(),
            _shutdown_waiter(),
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    node = SwarmNode()
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        logger.info("Node stopped via KeyboardInterrupt.")
    except SystemExit as e:
        logger.info(f"Node stopped: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
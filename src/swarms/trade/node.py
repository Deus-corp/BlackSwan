import asyncio
import hashlib
import logging
import math
import random
import signal
import socket
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.cognition import CuriosityEngine, MetaPOMDPAgent, SurvivalEvaluator
from src.evolution import GeneticEngine, Genome
from src.core.crdt_adapter import CRDTAdapter
from src.core.event_store import EventStore
from src.core.events import Event
from src.core.global_state import GlobalState
from src.core.gossip_adapter import SafeGossipAdapter
from src.swarms.trade.execution.controller import TradingController
from src.economy.roi_dispatcher import ROIDispatcher
from src.evolution.engine import EvolutionEngine
from src.evolution.mutation_engine import MutationEngine
from src.intelligence.episodic_memory import EpisodicMemory
from src.intelligence.internet_researcher import InternetResearcher
from src.intelligence.llm_client import LLMClient
from src.intelligence.semantic_memory import SemanticMemory
from src.memory.local_memory import LocalMemoryAPI, MemoryRecord
from src.observability.telemetry import Telemetry
from src.observability.telegram_notifier import TelegramNotifier
from src.risk.risk_manager import RiskManager
from src.security.crypto_manager import CryptoManager
from src.security.key_manager import KeyManager
from src.security.reputation_manager import ReputationManager
from swarm_config import config
from src.swarms.trade.adapters.multi_pair import MultiPairAdapter
from src.swarms.trade.adapters.orderbook import OrderBookAnalyzer
from src.swarms.trade.adapters.tradingview import TradingViewWebhook

from .context import RuntimeContext, TradeNodeConfig
from .maintenance.service import MaintenanceService
from .market.snapshot import MarketCollector, MarketSnapshot
from .meta.commands import apply_meta_commands
from .trading.flow import TradeFlowService
from dataclasses import replace

from collections.abc import Mapping

from src.swarms.trade.domain.capital import CapitalManager
from src.swarms.trade.domain.leader import select_leader
from src.swarms.trade.domain.mutation_metrics import (
    get_llm_stats,
    note_llm_mutation,
    update_llm_impact,
)
from src.swarms.trade.domain.swarm_sync import SwarmSync
from src.swarms.trade.heartbeat import HeartbeatPublisher
from src.swarms.trade.execution import build_backend
from src.swarms.trade.market import MarketSnapshotService

from src.swarms.common.protocols import (
    command_action,
    command_targets,
    normalize_command,
    command_is_expired,
)
from src.swarms.common.utils import is_expired

logger = logging.getLogger("SwarmNode")
trade_logger = logging.getLogger("SwarmNode.Trade")
logging.basicConfig(level=config.log_level)

EXPECTED_RETURN_RATE: float = config.expected_return_rate
MAX_NORMALIZED_CAPITAL: float = config.max_normalized_capital


class SwarmNode:
    """Single trade-swarm node coordinating market data, trading, memory, and evolution."""

    def __init__(self) -> None:
        # -----------------------------
        # Core node identity/config
        # -----------------------------
        self.node_id: str = str(config.NODE_ID)
        self.port: int = int(config.PORT)
        self.peers: List[str] = list(config.PEERS)

        self.node_index: int = abs(hash(socket.gethostname())) % max(1, int(config.total_nodes))
        logger.info("Node index: %s/%s", self.node_index, int(config.total_nodes))

        self.gossip_seq_no: int = 0
        self.gossip_lamport_ts: int = 0

        self.gossip_private_key: Ed25519PrivateKey = Ed25519PrivateKey.generate()
        self.gossip_public_bytes: bytes = self.gossip_private_key.public_key().public_bytes_raw()
        self.gossip_key_id: str = hashlib.sha256(self.gossip_public_bytes).hexdigest()[:16]

        self.market_url: Optional[str] = getattr(config, "MARKET_URL", None)
        self.market_mode: str = str(config.market_mode)

        self.burn_rate: float = float(config.BURN_RATE)
        self.failure_prob: float = float(config.FAILURE_PROB)
        self.gossip_interval: float = float(config.GOSSIP_INTERVAL)
        self.max_state: int = int(config.MAX_STATE)
        self.ttl: int = int(config.TTL)
        self.max_import: int = int(config.max_import)
        self.import_cooldown: int = int(config.IMPORT_COOLDOWN)

        self.memory_api_enabled: bool = bool(config.memory_api_enabled)

        self.trade_config: TradeNodeConfig = self._build_trade_config()

        # -----------------------------
        # Infrastructure layer
        # -----------------------------
        self.key_manager: KeyManager = KeyManager()
        self.crypto: CryptoManager = CryptoManager()
        self.reputation: ReputationManager = ReputationManager()
        self.reputation_blacklist_threshold: float = 0.3

        self.memory_api: LocalMemoryAPI = LocalMemoryAPI(
            node_id=self.node_id,
            storage=None,
        )

        self.internet_researcher: InternetResearcher = InternetResearcher(
            memory_api=self.memory_api if self.memory_api_enabled else None,
        )
        self.telegram_notifier: TelegramNotifier = TelegramNotifier()

        self.crdt: CRDTAdapter = CRDTAdapter(
            node_id=self.node_id,
            memory_api=self.memory_api if self.memory_api_enabled else None,
            reputation=self.reputation,
            db_path=config.crdt_db_path,
        )

        if self.memory_api_enabled:
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

        self.symbols_list: List[str] = list(self.trade_config.trading_symbols)
        self.market_adapter: MultiPairAdapter = MultiPairAdapter(
            symbols=self.symbols_list,
            market_mode=self.market_mode,
            crdt_adapter=self.crdt if self.market_mode == "web3" else None,
        )
        self.market_service: MarketSnapshotService = MarketSnapshotService(
            market_adapter=self.market_adapter,
            market_mode=self.market_mode,
        )

        if self.market_mode == "web3":
            for sym in self.symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter and hasattr(adapter, "crdt"):
                    adapter.crdt = self.crdt

        self.primary_symbol: str = self.symbols_list[0] if self.symbols_list else "BTC/USDT"

        self.tradingview_enabled: bool = bool(config.tradingview_webhook_enabled)
        self.tradingview_webhook: Optional[TradingViewWebhook] = None
        if self.tradingview_enabled:
            self.tradingview_webhook = TradingViewWebhook(port=int(config.tradingview_webhook_port))

        self.orderbook_enabled: bool = bool(config.orderbook_analysis_enabled)
        self.orderbook_analyzers: Dict[str, OrderBookAnalyzer] = {}
        if self.orderbook_enabled:
            for sym in self.symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter:
                    self.orderbook_analyzers[sym] = OrderBookAnalyzer(adapter)

        # -----------------------------
        # Intelligence layer
        # -----------------------------
        self.engine: GeneticEngine = GeneticEngine(pop_size=10)
        self.engine.initialize()

        self.state: GlobalState = GlobalState()
        best: Dict[str, Dict[str, float]] = self.state.get_best_genomes(top_n=1)
        self.current_params: Dict[str, float] = (
            list(best.values())[0]
            if best
            else {
                "max_risk_per_trade": 0.05,
                "phi_llm": 0.15,
                "stop_loss_ratio": 0.05,
                "trailing_stop_ratio": 0.01,
                "momentum_window": 10.0,
                "volatility_threshold": 0.02,
            }
        )

        self.dispatcher: ROIDispatcher = ROIDispatcher(config=self.current_params)

        self.survival: SurvivalEvaluator = SurvivalEvaluator()
        self.survival.dq = 0.03
        self.survival.liveness = 1.0

        self.curiosity: CuriosityEngine = CuriosityEngine(window_size=10, surprise_threshold=0.3)
        self.meta_agent: MetaPOMDPAgent = MetaPOMDPAgent()
        self.llm: LLMClient = LLMClient()

        self.memory: EpisodicMemory = EpisodicMemory(max_size=500)
        self.semantic: SemanticMemory = SemanticMemory()

        # -----------------------------
        # Runtime state
        # -----------------------------
        self.capital: float = 1000.0
        self.step_count: int = 0
        self.last_import_step: int = 0
        self._prev_price: float = 100.0
        self._prev_prev_price: float = 100.0
        self._last_market: Optional[Dict[str, Any]] = None
        self._trace_id: str = ""

        self.trading_controller: TradingController = TradingController(self.node_id)
        self.nonce_manager: Optional[Any] = None
        self.mutation_engine: MutationEngine = MutationEngine(
            self.llm,
            node_id=self.node_id,
            nonce_manager=self.nonce_manager,
            event_store=self.event_store,
        )

        self.evolution_engine: EvolutionEngine = EvolutionEngine(self)

        self.capital_manager: CapitalManager = CapitalManager(capital=self.capital)
        self.capital_manager.set_survival(self.survival)

        self.risk_manager: RiskManager = RiskManager()

        self.executor: Any = build_backend(
            node_id=self.node_id,
            adapter=None,
            is_leader_func=self.is_leader,
        )

        self.swarm_sync: SwarmSync = SwarmSync(self)

        self.shutdown_event: asyncio.Event = asyncio.Event()
        self._evolution_task: Optional[asyncio.Task[Any]] = None
        self._sync_task: Optional[asyncio.Task[Any]] = None
        self._command_task: Optional[asyncio.Task[Any]] = None
        self._paused: bool = False
        self._processed_command_gids: set[str] = set()

        # -----------------------------
        # Shared runtime context
        # -----------------------------
        self.ctx: RuntimeContext = self._build_runtime_context()

        # -----------------------------
        # Services built on top of the context
        # -----------------------------
        self.market_collector: MarketCollector = MarketCollector(self.ctx)
        self.trade_flow: TradeFlowService = TradeFlowService(self.ctx)
        self.maintenance_service: MaintenanceService = MaintenanceService(self.ctx)
        self.heartbeat_publisher: HeartbeatPublisher = HeartbeatPublisher(self.ctx)
        import inspect
        logger.info(
            "[%s] HeartbeatPublisher runtime class: module=%s file=%s signature=%s",
            self.node_id,
            self.heartbeat_publisher.__class__.__module__,
            inspect.getfile(self.heartbeat_publisher.__class__),
            inspect.signature(self.heartbeat_publisher.publish),
        )

        # Keep the shared context aligned with the node-owned service instances.
        self.ctx.market_collector = self.market_collector
        self.ctx.trade_flow = self.trade_flow
        self.ctx.maintenance_service = self.maintenance_service
        self.ctx.heartbeat_publisher = self.heartbeat_publisher
        self.sync_context()

        self._seed_from_memory()

    def _build_trade_config(self) -> TradeNodeConfig:
        trading_symbols_raw = str(getattr(config, "trading_symbols", ""))
        trading_symbols = [s.strip() for s in trading_symbols_raw.split(",") if s.strip()]

        return TradeNodeConfig(
            node_id=str(config.NODE_ID),
            port=int(config.PORT),
            peers=list(config.PEERS),
            total_nodes=int(config.total_nodes),
            market_mode=str(config.market_mode),
            market_url=getattr(config, "MARKET_URL", None),
            trading_symbols=trading_symbols,
            burn_rate=float(config.BURN_RATE),
            failure_prob=float(config.FAILURE_PROB),
            gossip_interval=float(config.GOSSIP_INTERVAL),
            max_state=int(config.MAX_STATE),
            ttl=int(config.TTL),
            max_import=int(config.max_import),
            import_cooldown=int(config.IMPORT_COOLDOWN),
            memory_api_enabled=bool(config.memory_api_enabled),
            tradingview_webhook_enabled=bool(config.tradingview_webhook_enabled),
            tradingview_webhook_port=int(config.tradingview_webhook_port),
            orderbook_analysis_enabled=bool(config.orderbook_analysis_enabled),
            expected_return_rate=float(config.expected_return_rate),
            max_normalized_capital=float(config.max_normalized_capital),
            capital_alert_threshold=float(config.capital_alert_threshold),
            capital_watchdog_threshold=float(config.capital_watchdog_threshold),
            hedge_ratio=float(config.hedge_ratio),
            test_web3_swap_side=str(config.trading.test_web3_swap_side),
            test_web3_swap_amount=float(config.trading.test_web3_swap_amount),
            log_level=str(config.log_level),
            execution_enabled=bool(getattr(config, "execution_enabled", False)),
            dry_run=bool(getattr(config, "dry_run", not bool(getattr(config, "execution_enabled", False)))),
        )

    def _build_runtime_context(self) -> RuntimeContext:
        return RuntimeContext(
            config=self.trade_config,
            crdt=self.crdt,
            reputation=self.reputation,
            telemetry=self.telemetry,
            event_store=self.event_store,
            memory_api=self.memory_api,
            capital_manager=self.capital_manager,
            risk_manager=self.risk_manager,
            survival=self.survival,
            curiosity=self.curiosity,
            llm=self.llm,
            memory=self.memory,
            semantic=self.semantic,
            key_manager=self.key_manager,
            crypto=self.crypto,
            market_adapter=self.market_adapter,
            market_service=self.market_service,
            market_collector=None,
            trading_controller=self.trading_controller,
            executor=self.executor,
            mutation_engine=self.mutation_engine,
            evolution_engine=self.evolution_engine,
            swarm_sync=self.swarm_sync,
            internet_researcher=self.internet_researcher,
            telegram_notifier=self.telegram_notifier,
            tradingview_webhook=self.tradingview_webhook,
            orderbook_analyzers=self.orderbook_analyzers,
            engine=self.engine,
            meta_agent=self.meta_agent,
            dispatcher=self.dispatcher,
            node_index=self.node_index,
            gossip_seq_no=self.gossip_seq_no,
            gossip_lamport_ts=self.gossip_lamport_ts,
            gossip_private_key=self.gossip_private_key,
            gossip_public_bytes=self.gossip_public_bytes,
            gossip_key_id=self.gossip_key_id,
            capital=self.capital,
            step_count=self.step_count,
            last_import_step=self.last_import_step,
            prev_price=self._prev_price,
            prev_prev_price=self._prev_prev_price,
            last_market=self._last_market,
            trace_id=self._trace_id,
            primary_symbol=self.primary_symbol,
            symbols_list=self.symbols_list,
            shutdown_event=self.shutdown_event,
            evolution_task=self._evolution_task,
            sync_task=self._sync_task,
            current_params=self.current_params,
        )

    def sync_context(self) -> None:
        self.ctx.capital = self.capital
        self.ctx.step_count = self.step_count
        self.ctx.last_import_step = self.last_import_step
        self.ctx.prev_price = self._prev_price
        self.ctx.prev_prev_price = self._prev_prev_price
        self.ctx.last_market = self._last_market
        self.ctx.trace_id = self._trace_id
        self.ctx.primary_symbol = self.primary_symbol
        self.ctx.symbols_list = self.symbols_list
        self.ctx.shutdown_event = self.shutdown_event
        self.ctx.evolution_task = self._evolution_task
        self.ctx.sync_task = self._sync_task
        self.ctx.current_params = self.current_params
        self.ctx.executor = self.executor
        self.ctx.market_adapter = self.market_adapter
        self.ctx.market_service = self.market_service
        self.ctx.trade_flow = self.trade_flow
        self.ctx.maintenance_service = self.maintenance_service
        self.ctx.heartbeat_publisher = self.heartbeat_publisher
        self.ctx.tradingview_webhook = self.tradingview_webhook
        self.ctx.orderbook_analyzers = self.orderbook_analyzers
        self.ctx.engine = self.engine
        self.ctx.meta_agent = self.meta_agent
        self.ctx.dispatcher = self.dispatcher
        self.ctx.market_collector = self.market_collector
        self.ctx.swarm_sync = self.swarm_sync

    def pull_context(self) -> None:
        self.capital = float(getattr(self.ctx, "capital", self.capital))
        self.step_count = int(getattr(self.ctx, "step_count", self.step_count))
        self.last_import_step = int(getattr(self.ctx, "last_import_step", self.last_import_step))
        self._prev_price = float(getattr(self.ctx, "prev_price", self._prev_price))
        self._prev_prev_price = float(getattr(self.ctx, "prev_prev_price", self._prev_prev_price))
        self._last_market = getattr(self.ctx, "last_market", self._last_market)
        self._trace_id = str(getattr(self.ctx, "trace_id", self._trace_id))

        current_params = getattr(self.ctx, "current_params", self.current_params)
        if isinstance(current_params, dict):
            self.current_params = current_params

        self.capital_manager.capital = self.capital

    def is_leader(self, block_number: int) -> bool:
        leader_index: int = select_leader(self.node_id, block_number, int(config.total_nodes))
        return self.node_index == leader_index

    async def _apply_meta_commands(self) -> None:
        commands: List[Dict[str, Any]] = []

        try:
            state = getattr(self.crdt, "state", {}) or {}
            for value in state.values():
                if not isinstance(value, dict):
                    continue

                item_type = str(value.get("type") or "")
                target_swarm = str(value.get("target_swarm") or value.get("swarm") or "")
                command_type = str(value.get("command_type") or value.get("action") or "")

                if item_type not in {"meta_command", "trade_command", "swarm_command"}:
                    continue
                if target_swarm not in {"", "*", "trade"}:
                    continue
                if not command_type:
                    continue

                commands.append(value)

            apply_meta_commands(self.ctx, commands)

        except Exception:
            logger.exception("[%s] Failed to apply trade meta commands.", self.node_id)

    async def _evolution_cycle(self) -> None:
        while True:
            try:
                await self._tick_evolution()
            except asyncio.CancelledError:
                logger.info("Evolution cycle task cancelled.")
                break
            except Exception as e:
                logger.error("Evolution cycle error: %s", e, exc_info=True)
            await asyncio.sleep(0.5)

    async def _sync_cycle(self) -> None:
        while True:
            try:
                await self._sync_swarm()
            except asyncio.CancelledError:
                logger.info("Sync cycle task cancelled.")
                break
            except Exception as e:
                logger.error("Sync cycle error: %s", e, exc_info=True)
            await asyncio.sleep(0.5)

    def node_niche(self) -> str:
        if self.survival.dq >= 0.8 or self.survival.liveness < 0.5:
            return "survival"
        if self.capital > 50000 and self.survival.dq < 0.3:
            return "capital"
        return "exploration"

    def accept_genome(self, genome: Dict[str, Any]) -> bool:
        try:
            if float(genome.get("fitness", 0.0)) < 0.001:
                return False
            for v in genome.get("params", {}).values():
                if not (0.0 < float(v) < 10.0):
                    return False
            pubkey_hex: Optional[str] = genome.get("origin_pubkey_hex")
            if pubkey_hex:
                pubkey_bytes: bytes = bytes.fromhex(pubkey_hex)
                if not self.reputation.is_trusted(pubkey_bytes):
                    return False
            return True
        except (ValueError, TypeError) as e:
            logger.debug("Failed to accept genome due to data conversion error: %s, genome=%s", e, genome)
            return False

    def make_genome(self, params: Dict[str, float], fitness: float) -> Dict[str, Any]:
        return {
            "params": params,
            "fitness": fitness,
            "niche": self.node_niche(),
            "origin": self.node_id,
            "lineage": [self.node_id],
            "ts": time.time(),
            "origin_pubkey_hex": self.crypto.public_bytes_hex,
        }

    def dict_to_genome(self, d: Dict[str, Any], niche: str = "exploration") -> Genome:
        genome_params: Dict[str, float] = {
            str(k): float(v)
            for k, v in d.get("params", {}).items()
            if isinstance(v, (int, float))
        }
        genome_fitness: float = float(d.get("fitness", 0.0))
        genome_niche: str = str(d.get("niche", niche))

        raw_lineage: Any = d.get("lineage", [])
        if not isinstance(raw_lineage, list):
            raw_lineage = []

        genome_lineage: List[str] = [str(item) for item in raw_lineage[-5:]] + [self.node_id]

        return Genome(
            params=genome_params,
            fitness=genome_fitness,
            niche=genome_niche,
            lineage=genome_lineage,
        )

    def local_score(self, genome: Genome) -> float:
        base: float = genome.fitness
        bias: float = 1.0
        if genome.niche == "survival":
            bias += min(0.5, self.survival.liveness)
        elif genome.niche == "exploration":
            bias += min(0.3, self.curiosity.surprise_threshold)
        elif genome.niche == "capital":
            bias += min(0.5, self.capital / 2000.0)

        if len(self.memory) > 0:
            vol: float = self._current_volatility()
            similar: List[MemoryRecord] = self.memory.find_similar(vol, self.survival.dq, top_k=5)
            for rec in similar:
                if isinstance(rec, dict) and isinstance(rec.get("params"), dict) and rec["params"] == genome.params:
                    bias += 0.2
                    break
        return base * bias

    def population_diversity(self) -> float:
        pop: List[Genome] = self.engine.population
        if not pop:
            return 0.0
        sigs = {frozenset(g.params.items()) for g in pop if isinstance(g, Genome)}
        return len(sigs) / len(pop)

    def population_niche_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {"survival": 0, "capital": 0, "exploration": 0}
        for g in self.engine.population:
            niche: str
            if isinstance(g, Genome):
                niche = g.niche
            elif isinstance(g, dict):
                niche = g.get("niche", "exploration")
            else:
                continue
            counts[niche] = counts.get(niche, 0) + 1
        return counts

    def _current_volatility(self) -> float:
        prev: float = getattr(self, "_prev_price", 100.0)
        prev_prev: float = getattr(self, "_prev_prev_price", 100.0)
        denominator: float = max(1.0, prev_prev)
        return abs(prev - prev_prev) / denominator

    def _seed_from_memory(self) -> None:
        if not self.memory.records:
            return
        current_volatility: float = self._current_volatility()
        similar: List[MemoryRecord] = self.memory.find_similar(current_volatility, self.survival.dq, top_k=3)
        for rec in similar:
            try:
                if isinstance(rec, dict) and "params" in rec and isinstance(rec["params"], dict):
                    genome: Genome = self.dict_to_genome({"params": rec["params"]})
                    self.engine.add_genome(genome)
            except Exception as e:
                logger.debug("Seed from memory skipped for record %s: %s", rec, e, exc_info=True)

    async def get_market_tick(self, session: aiohttp.ClientSession, symbol: str = "BTC/USDT") -> Dict[str, Any]:
        if self.market_mode == "live" and self.market_adapter:
            adapter = self.market_adapter.get_adapter(symbol)
            if adapter:
                tick: Optional[Dict[str, Any]] = await adapter.get_ticker()
                if tick is not None:
                    scale: float = float(config.trading.price_scale)
                    price_val: float = float(tick.get("price", tick.get("ask", 50000.0)))
                    tick["price"] = price_val / scale
                    tick["symbol"] = symbol
                    return tick

        if self.market_url:
            try:
                async with session.get(self.market_url, timeout=1) as resp:
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientError as e:
                logger.debug("Market URL request failed (ClientError) for %s: %s", self.market_url, e)
            except asyncio.TimeoutError:
                logger.debug("Market URL request to %s timed out.", self.market_url)
            except Exception as e:
                logger.debug("Market URL request failed (Generic Error) for %s: %s", self.market_url, e)

        logger.warning("Could not get market data for %s, using simulated fallback price.", symbol)
        return {"price": random.uniform(90.0, 110.0), "symbol": symbol, "timestamp": time.time()}

    async def _handle_market_mode_logic(self, best_symbol: str, best_market: Dict[str, Any]) -> None:
        if self.market_mode == "web3":
            adapter = self.market_adapter.get_adapter(best_symbol)
            if adapter and hasattr(adapter, "w3"):
                try:
                    block_number: int = await adapter.w3.eth.block_number
                    if self.is_leader(block_number):
                        await self.trading_controller.check_and_rebalance(adapter)
                except Exception as e:
                    logger.warning("Web3 rebalance check failed for %s: %s", best_symbol, e, exc_info=True)

        if self.market_mode == "futures":
            adapter = self.market_adapter.get_adapter(best_symbol, "futures")
            if adapter and hasattr(adapter, "exchange") and hasattr(adapter, "check_stop_loss"):
                try:
                    positions: List[Dict[str, Any]] = await adapter.exchange.fetch_positions([best_symbol])
                    if positions:
                        pos: Dict[str, Any] = positions[0]
                        contracts_str: Any = pos.get("contracts", "0.0")
                        contracts: float = float(contracts_str)
                        if contracts != 0.0:
                            entry_price: float = float(pos.get("entryPrice", 0.0))
                            current_price: float = float(best_market["price"])
                            side: str = "long" if contracts > 0 else "short"
                            if adapter.check_stop_loss(entry_price, current_price, side):
                                logger.info("Stop-loss triggered for %s", best_symbol)
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
                                            logger.info("Hedge position for %s closed.", best_symbol)
                                        except Exception as e:
                                            logger.warning("Hedge position close failed for %s: %s", best_symbol, e)
                except Exception as e:
                    logger.warning("Futures stop-loss check failed for %s: %s", best_symbol, e, exc_info=True)

    async def _maybe_trigger_failure_shutdown(self) -> bool:
        if self.failure_prob > 0 and random.random() < self.failure_prob:
            await self.telemetry.spore_failure(
                step=self.step_count,
                capital=self.capital,
                dq=self.survival.dq,
                fitness=float(self.engine.champion[1]) if self.engine.champion else 0.0,
                diversity=self.engine.diversity(),
                crdt_size=len(self.crdt.state),
                trace_id=self._trace_id,
            )
            logger.info("[%s] simulated failure, initiating graceful shutdown.", self.node_id)
            self.shutdown_event.set()
            return True
        return False
    
    def _apply_capital_burn_and_check_alive(self) -> bool:
        self.capital_manager.burn()
        self.capital = self.capital_manager.capital
        self.ctx.capital = self.capital

        if not self.capital_manager.is_alive():
            logger.info("[%s] died due to insufficient capital. Initiating graceful shutdown.", self.node_id)
            self.shutdown_event.set()
            return False

        return True
    
    async def _run_one_step(self, session: aiohttp.ClientSession) -> bool:
        self.step_count += 1
        self._trace_id = str(uuid.uuid4())
        if self._paused:
            logger.debug("[%s] Trade node paused; skipping trading step.", self.node_id)
            await asyncio.sleep(0.5)
            return True

        if await self._maybe_trigger_failure_shutdown():
            return False

        snapshot: MarketSnapshot = await self.market_collector.collect(session)
        best_symbol: str = snapshot.best_symbol
        best_market: Dict[str, Any] = snapshot.best_market

        self._prev_prev_price = self._prev_price
        self._prev_price = float(best_market.get("price", 100.0))
        self._last_market = best_market

        self.sync_context()

        await self._handle_market_mode_logic(best_symbol, best_market)

        if not self._apply_capital_burn_and_check_alive():
            return False

        await self.trade_flow.process(snapshot)
        self.pull_context()
        self._last_market = best_market

        await self._periodic_tasks(snapshot)

        self.telemetry.update_impact(self.capital)
        alert_threshold: float = float(config.capital_alert_threshold)
        if self.capital < alert_threshold:
            await self.telemetry.low_capital_alert(self.capital, alert_threshold)

        return True

    async def main_loop(self) -> None:
        async with aiohttp.ClientSession() as session:
            if self.memory_api_enabled:
                await self.memory_api.load_from_db()

            while not self.shutdown_event.is_set():
                should_continue = await self._run_one_step(session)
                if not should_continue:
                    break
                await asyncio.sleep(0.5)

            logger.info("[%s] Main loop exited gracefully.", self.node_id)

    async def _collect_market_snapshot(self, session: aiohttp.ClientSession) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Compatibility helper retained while the refactor settles."""
        snapshot: MarketSnapshot = await self.market_collector.collect(session)
        return snapshot.best_symbol, snapshot.best_market, snapshot.markets

    async def _evaluate_survival_and_trade(self, market: Dict[str, Any], symbol: str) -> Optional[Dict[str, Any]]:
        snapshot = MarketSnapshot(
            best_symbol=symbol,
            best_market=market,
            markets={symbol: dict(market)},
            timestamp=time.time(),
        )
        return await self.trade_flow.process(snapshot)

    def _recombine(self, g1: Dict[str, Any], g2: Dict[str, Any]) -> Dict[str, Any]:
        all_keys: set[str] = set(g1.get("params", {}).keys()) | set(g2.get("params", {}).keys())
        child_params: Dict[str, float] = {}
        for k in all_keys:
            v1: float = float(g1.get("params", {}).get(k, 0.5))
            v2: float = float(g2.get("params", {}).get(k, 0.5))
            val: float = v1 if random.random() < 0.5 else v2
            if random.random() < 0.1:
                val *= random.uniform(0.9, 1.1)
            val = max(0.0001, min(10.0, val))
            child_params[k] = val

        child_niche: str = g1.get("niche", "exploration") if random.random() < 0.5 else g2.get("niche", "exploration")
        lineage1 = [str(item) for item in g1.get("lineage", [])[-5:]]
        lineage2 = [str(item) for item in g2.get("lineage", [])[-5:]]
        child_lineage: List[str] = (lineage1 if random.random() < 0.5 else lineage2) + [self.node_id]

        return {
            "params": child_params,
            "fitness": 0.0,
            "niche": child_niche,
            "origin": self.node_id,
            "lineage": child_lineage,
            "ts": time.time(),
            "origin_pubkey_hex": self.crypto.public_bytes_hex,
        }

    async def _tick_evolution(self) -> None:
        if self._last_market:
            await self.evolution_engine.tick(self._last_market)
        else:
            logger.debug("Skipping evolution tick: _last_market not available yet.")

    async def _sync_swarm(self) -> None:
        await self.swarm_sync.reconcile()

    async def _periodic_tasks(self, snapshot: MarketSnapshot) -> None:
        if self.step_count % 50 == 0:
            await self._apply_meta_commands()

        if self.step_count % 10 == 0:
            self.sync_context()
            try:
                await self.heartbeat_publisher.publish(snapshot)
            except Exception:
                logger.exception("[%s] Failed to publish trade heartbeat.", self.node_id)

        if (
            self.step_count % 200 == 0
            or self.step_count % 500 == 0
            or self.capital < float(config.capital_watchdog_threshold)
        ):
            self.sync_context()
            await self.maintenance_service.run(self.current_params)

    async def _emit_trade_event(
        self,
        *,
        event_type: str,
        parent_gid: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        event: Dict[str, Any] = {
            "type": "swarm_event",
            "swarm": "trade",
            "node_id": self.node_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "payload": payload or {},
        }
        if parent_gid:
            event["parent_gid"] = parent_gid

        try:
            await self.crdt.add_genome(event)
        except Exception:
            logger.exception("Failed to emit trade event %s", event_type)

    def _command_applies_to_self(self, normalized: Dict[str, Any]) -> bool:
        payload = normalized.get("payload") if isinstance(normalized.get("payload"), Mapping) else {}
        data = normalized.get("data") if isinstance(normalized.get("data"), Mapping) else {}

        def pick(*keys: str) -> Any:
            for source in (normalized, payload, data):
                for key in keys:
                    value = source.get(key)
                    if value not in (None, ""):
                        return value
            return None

        target_swarm = pick("target_swarm", "swarm")
        target_node = pick("target_node", "target_node_id", "node_id")
        target_role = pick("target_role", "role")

        if str(target_swarm or "").strip() not in {"", "*", "trade"}:
            return False

        if str(target_node or "").strip() not in {"", "*", self.node_id}:
            return False

        if str(target_role or "").strip() not in {"", "*", "node", "trade_node", "maintenance_agent"}:
            return False

        return True

    def _command_has_explicit_approval(self, normalized: Dict[str, Any]) -> bool:
        payload = normalized.get("payload") if isinstance(normalized.get("payload"), Mapping) else {}
        data = normalized.get("data") if isinstance(normalized.get("data"), Mapping) else {}

        explicit_approval = bool(
            normalized.get("explicit_approval")
            or payload.get("explicit_approval")
            or data.get("explicit_approval")
        )
        safety_gate = str(
            normalized.get("safety_gate")
            or payload.get("safety_gate")
            or data.get("safety_gate")
            or ""
        ).lower()

        return explicit_approval and safety_gate in {"approved", "allow", "enabled"}

    def _command_value(self, normalized: Dict[str, Any], key: str, default: Any = None) -> Any:
        payload = normalized.get("payload") if isinstance(normalized.get("payload"), Mapping) else {}
        data = normalized.get("data") if isinstance(normalized.get("data"), Mapping) else {}

        if key in payload:
            return payload.get(key)
        if key in data:
            return data.get(key)
        if key in normalized:
            return normalized.get(key)
        return default

    def _command_action(self, normalized: Dict[str, Any]) -> str:
        payload = normalized.get("payload") if isinstance(normalized.get("payload"), Mapping) else {}
        data = normalized.get("data") if isinstance(normalized.get("data"), Mapping) else {}

        action = (
            command_action(normalized)
            or normalized.get("command_type")
            or normalized.get("action")
            or normalized.get("command")
            or payload.get("command_type")
            or payload.get("action")
            or payload.get("command")
            or data.get("command_type")
            or data.get("action")
            or data.get("command")
        )
        return str(action or "").strip().upper()

    async def process_command(self, command: Mapping[str, Any]) -> None:
        normalized = normalize_command(command)

        gid = str(normalized.get("gid") or command.get("gid") or "")
        if gid and gid in self._processed_command_gids:
            return

        if command_is_expired(normalized):
            if gid:
                self._processed_command_gids.add(gid)
            return

        if not self._command_applies_to_self(normalized):
            return

        action = self._command_action(normalized)
        if not action:
            return

        if gid:
            self._processed_command_gids.add(gid)

        if action == "PAUSE":
            self._paused = True
            await self._emit_trade_event(
                event_type="command_applied",
                parent_gid=gid or None,
                payload={"action": action, "status": "paused"},
            )
            logger.info("[%s] Trade node paused by command.", self.node_id)
            return

        if action == "RESUME":
            self._paused = False
            await self._emit_trade_event(
                event_type="command_applied",
                parent_gid=gid or None,
                payload={"action": action, "status": "resumed"},
            )
            logger.info("[%s] Trade node resumed by command.", self.node_id)
            return

        if action == "RESTART_NODE":
            await self._emit_trade_event(
                event_type="command_applied",
                parent_gid=gid or None,
                payload={"action": action, "status": "shutdown_requested"},
            )
            logger.critical("[%s] Received RESTART_NODE. Requesting shutdown.", self.node_id)
            self.shutdown_event.set()
            return

        if action == "SET_DRY_RUN":
            value = self._command_value(normalized, "enabled", self._command_value(normalized, "value", True))
            dry_run = bool(value)
            self.trade_config = replace(
                self.trade_config,
                dry_run=dry_run,
                execution_enabled=False if dry_run else self.trade_config.execution_enabled,
            )
            self.ctx.config = self.trade_config
            await self._emit_trade_event(
                event_type="command_applied",
                parent_gid=gid or None,
                payload={
                    "action": action,
                    "dry_run": self.trade_config.dry_run,
                    "execution_enabled": self.trade_config.execution_enabled,
                },
            )
            return

        if action == "SET_EXECUTION_ENABLED":
            value = bool(self._command_value(normalized, "enabled", self._command_value(normalized, "value", False)))

            if value and not self._command_has_explicit_approval(normalized):
                await self._emit_trade_event(
                    event_type="command_blocked",
                    parent_gid=gid or None,
                    payload={
                        "action": action,
                        "reason": "explicit_approval_required",
                        "execution_enabled": self.trade_config.execution_enabled,
                        "dry_run": self.trade_config.dry_run,
                    },
                )
                logger.warning("[%s] Blocked SET_EXECUTION_ENABLED without approval.", self.node_id)
                return

            self.trade_config = replace(
                self.trade_config,
                execution_enabled=value,
                dry_run=False if value else True,
            )
            self.ctx.config = self.trade_config
            await self._emit_trade_event(
                event_type="command_applied",
                parent_gid=gid or None,
                payload={
                    "action": action,
                    "execution_enabled": self.trade_config.execution_enabled,
                    "dry_run": self.trade_config.dry_run,
                },
            )
            return

        await self._emit_trade_event(
            event_type="command_unsupported",
            parent_gid=gid or None,
            payload={"action": action},
        )

    async def _command_loop(self) -> None:
        while not self.shutdown_event.is_set():
            try:
                state = getattr(self.crdt, "state", {})
                for value in list(state.values()):
                    if not isinstance(value, Mapping):
                        continue
                    if value.get("type") not in {"swarm_command", "trade_command"}:
                        continue
                    await self.process_command(value)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[%s] command loop failed", self.node_id)

            await asyncio.sleep(1.0)

    async def _graceful_shutdown(self) -> None:
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

        if self._command_task:
            self._command_task.cancel()
            try:
                await self._command_task
            except asyncio.CancelledError:
                logger.debug("Command task cancelled.")

        if self.memory_api_enabled:
            await self.memory_api.save_to_db()
            logger.info("[%s] Memory saved before exit.", self.node_id)

        if self.tradingview_enabled and self.tradingview_webhook:
            await self.tradingview_webhook.stop()
            logger.info("[%s] TradingView webhook stopped.", self.node_id)

        if self.telegram_notifier:
            try:
                close = getattr(self.telegram_notifier, "close", None)
                if callable(close):
                    result = close()
                    if asyncio.iscoroutine(result):
                        await result
                    logger.info("[%s] Telegram notifier closed.", self.node_id)
            except Exception:
                logger.exception("[%s] Failed to close Telegram notifier.", self.node_id)

        if self.market_adapter:
            try:
                if hasattr(self.market_adapter, "close") and callable(self.market_adapter.close):
                    result = self.market_adapter.close()
                    if asyncio.iscoroutine(result):
                        await result
                    logger.info("[%s] Market adapter closed.", self.node_id)
            except Exception:
                logger.exception("[%s] Failed to close market adapter.", self.node_id)

        if hasattr(self.crdt, "close") and callable(self.crdt.close):
            await self.crdt.close()
            logger.info("[%s] CRDT resources closed.", self.node_id)

    async def _initialize_web3_executor(self) -> None:
        if self.market_mode != "web3":
            return

        first_adapter_for_executor: Optional[Any] = None
        for sym in self.symbols_list:
            adapter = self.market_adapter.get_adapter(sym)
            if not adapter:
                continue

            if hasattr(adapter, "initialize") and callable(adapter.initialize):
                logger.info("Initializing web3 adapter for %s...", sym)
                await adapter.initialize()

            if self.nonce_manager is None and hasattr(adapter, "nonce_manager"):
                self.nonce_manager = getattr(adapter, "nonce_manager")
                self.mutation_engine.nonce_manager = self.nonce_manager

            if first_adapter_for_executor is None:
                first_adapter_for_executor = adapter

        self.executor = build_backend(self.node_id, first_adapter_for_executor, self.is_leader)
        self.ctx.executor = self.executor
        logger.info(
            "[%s] Web3 backend initialized with adapter: %s.",
            self.node_id,
            type(first_adapter_for_executor).__name__ if first_adapter_for_executor else "None",
        )

    def _register_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        def _shutdown_handler(*args: Any) -> None:
            logger.info(
                "[%s] received signal %s (%s), initiating graceful shutdown.",
                self.node_id,
                args[0],
                signal.Signals(args[0]).name,
            )
            self.shutdown_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _shutdown_handler, sig)
            except NotImplementedError:
                logger.warning(
                    "Signal handler for %s not available on this platform.",
                    signal.Signals(sig).name,
                )
            except Exception as e:
                logger.error("Error adding signal handler for %s: %s", signal.Signals(sig).name, e)

    async def _shutdown_watcher(self) -> None:
        await self.shutdown_event.wait()
        logger.info("[%s] Shutdown signal received, initiating cleanup.", self.node_id)

        await self._graceful_shutdown()

        raise SystemExit(0)

    async def start(self) -> None:
        logger.info("[%s] starting on port=%s, peers=%s", self.node_id, self.port, self.peers)

        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

        if self.tradingview_enabled and self.tradingview_webhook:
            await self.tradingview_webhook.start()

        self._register_signal_handlers(loop)

        await self._initialize_web3_executor()

        self.sync_context()
        self._evolution_task = asyncio.create_task(self._evolution_cycle(), name="evolution_cycle")
        self._sync_task = asyncio.create_task(self._sync_cycle(), name="sync_cycle")
        self._command_task = asyncio.create_task(self._command_loop(), name="command_loop")
        self.sync_context()

        # Publish an initial heartbeat before entering the main loop so the
        # overseer can discover the trade node during its first collection cycle.
        try:
            await self.heartbeat_publisher.publish()
        except Exception:
            logger.exception("[%s] Failed to publish initial trade heartbeat.", self.node_id)

        try:
            await self.main_loop()
        finally:
            self.shutdown_event.set()
            await self._graceful_shutdown()
        
if __name__ == "__main__":
    if not logging.root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        logging.getLogger().setLevel(logging.INFO)

    node = SwarmNode()
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        logger.info("Node process interrupted by KeyboardInterrupt.")
    except SystemExit as e:
        logger.info("Node process stopped gracefully: %s", e)
    except Exception as e:
        logger.error("An unexpected critical error occurred during node execution: %s", e, exc_info=True)

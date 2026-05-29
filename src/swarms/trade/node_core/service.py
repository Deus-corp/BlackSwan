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
from src.security.crypto_manager import CryptoManager
from src.security.key_manager import KeyManager
from src.security.reputation_manager import ReputationManager
from swarm_config import config
from src.swarms.trade.adapters.multi_pair import MultiPairAdapter
from src.swarms.trade.adapters.orderbook import OrderBookAnalyzer
from src.swarms.trade.adapters.tradingview import TradingViewWebhook
from src.swarms.trade.risk import PositionSizer, RiskManager, TradePolicy
from dataclasses import replace

from src.swarms.trade.context import RuntimeContext, TradeNodeConfig
from src.swarms.trade.maintenance.service import MaintenanceService
from src.swarms.trade.market.snapshot import MarketCollector, MarketSnapshot
from src.swarms.trade.meta.commands import apply_meta_commands
from src.swarms.trade.trading.flow import TradeFlowService
from src.swarms.trade.node_core.command_processor import process_trade_command

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
from src.swarms.trade.node_core.run_step import run_one_step as runtime_run_one_step

from src.swarms.common.protocols import (
    command_action,
    command_targets,
    normalize_command,
    command_is_expired,
)
from src.swarms.common.utils import is_expired

from src.swarms.trade.node_core.commands import (
    command_action as trade_command_action,
    command_applies_to_node,
    command_has_explicit_approval,
    command_value as trade_command_value,
)
from src.swarms.trade.node_core.events import emit_trade_event

from src.swarms.trade.node_core.loop import (
    collect_market_snapshot as loop_collect_market_snapshot,
    evaluate_survival_and_trade as loop_evaluate_survival_and_trade,
    periodic_tasks as loop_periodic_tasks,
    sync_swarm as loop_sync_swarm,
    tick_evolution as loop_tick_evolution,
)

from src.swarms.trade.node_core.evolution import (
    accept_genome as evolution_accept_genome,
    current_volatility as evolution_current_volatility,
    dict_to_genome as evolution_dict_to_genome,
    local_score as evolution_local_score,
    make_genome as evolution_make_genome,
    node_niche as evolution_node_niche,
    population_diversity as evolution_population_diversity,
    population_niche_counts as evolution_population_niche_counts,
    recombine as evolution_recombine,
    seed_from_memory as evolution_seed_from_memory,
)

from src.swarms.trade.node_core.step import (
    apply_capital_burn_and_check_alive as step_apply_capital_burn_and_check_alive,
    maybe_trigger_failure_shutdown as step_maybe_trigger_failure_shutdown,
)

from src.swarms.trade.node_core.market_mode import (
    handle_market_mode_logic as market_mode_handle_market_mode_logic,
)

from src.swarms.trade.node_core.runtime import (
    graceful_shutdown as runtime_graceful_shutdown,
    register_signal_handlers as runtime_register_signal_handlers,
    run_main_loop as runtime_run_main_loop,
    run_node_start as runtime_run_node_start,
    shutdown_watcher as runtime_shutdown_watcher,
)

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
        return evolution_node_niche(self)

    def accept_genome(self, genome: Dict[str, Any]) -> bool:
        return evolution_accept_genome(self, genome)

    def make_genome(self, params: Dict[str, float], fitness: float) -> Dict[str, Any]:
        return evolution_make_genome(self, params, fitness)

    def dict_to_genome(self, d: Dict[str, Any], niche: str = "exploration") -> Genome:
        return evolution_dict_to_genome(self, d, niche)

    def local_score(self, genome: Genome) -> float:
        return evolution_local_score(self, genome)

    def population_diversity(self) -> float:
        return evolution_population_diversity(self)

    def population_niche_counts(self) -> Dict[str, int]:
        return evolution_population_niche_counts(self)

    def _current_volatility(self) -> float:
        return evolution_current_volatility(self)

    def _seed_from_memory(self) -> None:
        evolution_seed_from_memory(self)

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
        await market_mode_handle_market_mode_logic(self, best_symbol, best_market)

    async def _maybe_trigger_failure_shutdown(self) -> bool:
        return await step_maybe_trigger_failure_shutdown(self)
    
    def _apply_capital_burn_and_check_alive(self) -> bool:
        return step_apply_capital_burn_and_check_alive(self)
    
    async def _run_one_step(self, session: aiohttp.ClientSession) -> bool:
        return await runtime_run_one_step(self, session)

    async def main_loop(self) -> None:
        await runtime_run_main_loop(self)

    async def _collect_market_snapshot(
        self,
        session: aiohttp.ClientSession,
    ) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        return await loop_collect_market_snapshot(self, session)

    async def _evaluate_survival_and_trade(
        self,
        market: Dict[str, Any],
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        return await loop_evaluate_survival_and_trade(self, market, symbol)

    def _recombine(self, g1: Dict[str, Any], g2: Dict[str, Any]) -> Dict[str, Any]:
        return evolution_recombine(self, g1, g2)

    async def _tick_evolution(self) -> None:
        await loop_tick_evolution(self)

    async def _sync_swarm(self) -> None:
        await loop_sync_swarm(self)

    async def _periodic_tasks(self, snapshot: MarketSnapshot) -> None:
        await loop_periodic_tasks(self, snapshot)

    async def _emit_trade_event(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        parent_gid: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> Event:
        return await emit_trade_event(
            event_bus=getattr(self, "event_bus", None),
            event_store=getattr(self, "event_store", None),
            crdt=getattr(self, "crdt", None),
            node_id=self.node_id,
            event_type=event_type,
            payload=payload,
            parent_id=parent_id or parent_gid,
        )

    def _command_applies_to_self(self, normalized: Dict[str, Any]) -> bool:
        return command_applies_to_node(normalized, node_id=self.node_id, target_swarm="trade")

    def _command_has_explicit_approval(self, normalized: Dict[str, Any]) -> bool:
        return command_has_explicit_approval(normalized)

    def _command_value(self, normalized: Dict[str, Any], key: str, default: Any = None) -> Any:
        return trade_command_value(normalized, key, default)

    def _command_action(self, normalized: Dict[str, Any]) -> str:
        return trade_command_action(normalized)

    async def process_command(self, command: Mapping[str, Any]) -> None:
        await process_trade_command(self, command)

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

    async def _graceful_shutdown_impl(self) -> None:
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

    async def _graceful_shutdown(self) -> None:
        await runtime_graceful_shutdown(self)

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

    def _register_signal_handlers_impl(self, loop: asyncio.AbstractEventLoop) -> None:
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

    def _register_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        runtime_register_signal_handlers(self, loop)

    async def _shutdown_watcher(self) -> None:
        await runtime_shutdown_watcher(self)

    async def _start_impl(self) -> None:
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

    async def start(self) -> None:
        await runtime_run_node_start(self)

async def main() -> None:
    """Run the trade swarm node service."""
    if not logging.root.handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    else:
        logging.getLogger().setLevel(logging.INFO)

    node = SwarmNode()
    try:
        await node.start()
    except KeyboardInterrupt:
        logger.info("Node process interrupted by KeyboardInterrupt.")
    except SystemExit as exc:
        logger.info("Node process stopped gracefully: %s", exc)
    except Exception as exc:
        logger.error("An unexpected critical error occurred during node execution: %s", exc, exc_info=True)
        raise
        
if __name__ == "__main__":
    asyncio.run(main())
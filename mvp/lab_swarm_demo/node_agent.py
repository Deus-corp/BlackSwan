import os, time, random, uuid, hashlib, asyncio, logging, sys, signal, socket
from typing import Dict, Any, Optional, List, Tuple

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
from src.security.gossip_envelope import sign_envelope, generate_key_pair, public_key_bytes, sha256
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
# Вынесенные счётчики мутаций
from mvp.lab_swarm_demo.mutation_metrics import note_llm_mutation, update_llm_impact, get_llm_stats, _llm_mutation_count

logger = logging.getLogger("SwarmNode")
trade_logger = logging.getLogger("SwarmNode.Trade")
logging.basicConfig(level=config.log_level)

EXPECTED_RETURN_RATE = config.expected_return_rate
MAX_NORMALIZED_CAPITAL = config.max_normalized_capital

# Все глобальные переменные и функции удалены из этого файла


class SwarmNode:
    def __init__(self) -> None:
        # конфигурация
        self.node_id: str = config.NODE_ID
        self.port: int = config.PORT
        self.peers: List[str] = config.PEERS

        self.node_index = abs(hash(socket.gethostname())) % config.total_nodes
        logger.info(f"Node index: {self.node_index}/{config.total_nodes}")

        self.gossip_seq_no = 0
        self.gossip_lamport_ts = 0

        # Gossip signing keys
        self.gossip_private_key = Ed25519PrivateKey.generate()
        self.gossip_public_bytes = self.gossip_private_key.public_key().public_bytes_raw()
        self.gossip_key_id = hashlib.sha256(self.gossip_public_bytes).hexdigest()[:16]

        self.market_url: Optional[str] = config.MARKET_URL
        self.market_mode: str = config.market_mode

        self.burn_rate: float = config.BURN_RATE
        self.failure_prob: float = config.FAILURE_PROB
        self.gossip_interval: float = config.GOSSIP_INTERVAL
        self.max_state: int = config.MAX_STATE
        self.ttl: int = config.TTL
        self.max_import: int = config.MAX_IMPORT
        self.import_cooldown: int = config.IMPORT_COOLDOWN

        self.swarm_sync = SwarmSync(self)

        # ========== INFRASTRUCTURE LAYER (BODY) ==========
        self.key_manager = KeyManager()
        self.crypto: CryptoManager = CryptoManager()

        self.reputation: ReputationManager = ReputationManager()
        self.reputation_blacklist_threshold: float = 0.3

        self.memory_api_enabled: bool = config.memory_api_enabled
        self.memory_api: LocalMemoryAPI = LocalMemoryAPI(
            node_id=self.node_id,
            storage=None
        )

        self.internet_researcher: InternetResearcher = InternetResearcher(
            memory_api=self.memory_api if self.memory_api_enabled else None
        )
        self.telegram_notifier = TelegramNotifier()

        self.crdt: CRDTAdapter = CRDTAdapter(
            node_id=self.node_id,
            memory_api=self.memory_api if self.memory_api_enabled else None,
            reputation=self.reputation
        )

        if self.memory_api_enabled:
            self.memory_api.storage = self.crdt.storage

        self.gossip: SafeGossipAdapter = SafeGossipAdapter(self.crdt)
        self.gossip.set_reputation_manager(self.reputation)

        self.event_store = EventStore(
            ledger_path=config.event_ledger_path,
            sqlite_path=config.event_sqlite_path,
        )

        self.telemetry = Telemetry(
            node_id=self.node_id,
            event_store=self.event_store,
            telegram_notifier=self.telegram_notifier,
            get_llm_stats_func=get_llm_stats,
            update_llm_impact_func=update_llm_impact,
        )

        trading_symbols = config.trading_symbols
        symbols_list = [s.strip() for s in trading_symbols.split(",") if s.strip()]
        self.symbols_list = symbols_list
        self.market_adapter = MultiPairAdapter(
            symbols=symbols_list,
            market_mode=self.market_mode,
            crdt_adapter=self.crdt if self.market_mode == "web3" else None
        )
        self.market_service = MarketSnapshotService(
            market_adapter=self.market_adapter,
            market_mode=self.market_mode,
        )

        if self.market_mode == "web3":
            for sym in symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter and hasattr(adapter, 'crdt'):
                    adapter.crdt = self.crdt

        self.primary_symbol = symbols_list[0] if symbols_list else "BTC/USDT"

        self.tradingview_enabled = config.tradingview_webhook_enabled
        self.tradingview_webhook = None
        if self.tradingview_enabled:
            self.tradingview_webhook = TradingViewWebhook(port=config.tradingview_webhook_port)

        self.orderbook_enabled = config.orderbook_analysis_enabled
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
        best = self.state.get_best_genomes(top_n=1)
        self.current_params: Dict[str, float] = list(best.values())[-1] if best else {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
        self.dispatcher = ROIDispatcher(config=self.current_params)

        self.survival: SurvivalEvaluator = SurvivalEvaluator()
        self.survival.dq = 0.03
        self.survival.liveness = 1.0

        self.curiosity: CuriosityEngine = CuriosityEngine(window_size=10, surprise_threshold=0.3)
        self.meta_agent: MetaPOMDPAgent = MetaPOMDPAgent()
        self.llm = LLMClient()

        self.memory: EpisodicMemory = EpisodicMemory(max_size=500)
        self.semantic: SemanticMemory = SemanticMemory()

        # ========== RUNTIME STATE ==========
        self.capital: float = 1000.0
        self.step_count: int = 0
        self.last_import_step: int = 0
        self._prev_price: float = 100.0
        self._prev_prev_price: float = 100.0

        self._seed_from_memory()

        self.trading_controller = TradingController(self.node_id)
        self.mutation_engine = MutationEngine(self.llm, node_id=self.node_id, nonce_manager=None, event_store=self.event_store)
        self.nonce_manager = None
        self.evolution_engine = EvolutionEngine(self)

        self.capital_manager = CapitalManager(capital=self.capital)
        self.capital_manager.set_survival(self.survival)

        self.executor = build_backend(
            node_id=self.node_id,
            adapter=None,
            is_leader_func=self.is_leader,
        )

    def is_leader(self, block_number: int) -> bool:
        leader_index = select_leader(self.node_id, block_number, config.total_nodes)
        return self.node_index == leader_index
    
    async def _apply_meta_commands(self):
        try:
            all_state = self.crdt.state
            # --- Обработка структурированных JSON-команд ---
            json_commands = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "meta_command_json"]
            if json_commands:
                latest_json = max(json_commands, key=lambda x: x.get("timestamp", 0))
                data = latest_json.get("data", {})
                if data.get("action") == "ADJUST_SWARM":
                    params = data.get("params", {})
                    alpha = 0.1
                    import math

                    if "risk_scale" in params:
                        raw = params["risk_scale"]
                        adjustment = alpha * math.tanh(raw - 1.0)
                        old_risk = self.current_params.get("max_risk_per_trade", 0.05)
                        new_risk = old_risk * (1 + adjustment)
                        new_risk = max(0.005, min(0.15, new_risk))
                        self.current_params["max_risk_per_trade"] = new_risk
                        logger.info(f"🧠 MetaAgent JSON: risk {old_risk:.4f} → {new_risk:.4f}")

                    if "exploration_multiplier" in params:
                        mult = params["exploration_multiplier"]
                        old_rate = getattr(self.engine, '_mutation_rate', 0.25)
                        new_rate = max(0.1, min(0.7, old_rate * mult))
                        if hasattr(self.engine, 'set_mutation_rate'):
                            self.engine.set_mutation_rate(new_rate)
                        logger.info(f"🧠 MetaAgent JSON: exploration rate → {new_rate:.2f}")

                    if "survival_bias_adj" in params:
                        delta = max(-0.05, min(0.05, params["survival_bias_adj"]))
                        old_sb = self.survival.config.get("lambda", 0.15)
                        new_sb = max(0.1, min(0.9, old_sb + delta))
                        self.survival.config["lambda"] = new_sb
                        logger.info(f"🧠 MetaAgent JSON: survival lambda → {new_sb:.3f}")

                    if "stop_loss_adj" in params:
                        factor = params["stop_loss_adj"]
                        old_sl = self.current_params.get("stop_loss_ratio", 0.05)
                        new_sl = max(0.001, min(0.2, old_sl * factor))
                        self.current_params["stop_loss_ratio"] = new_sl
                        logger.info(f"🧠 MetaAgent JSON: stop-loss {old_sl:.4f} → {new_sl:.4f}")

            # --- Fallback к текстовым командам ---
            text_commands = [v for k, v in all_state.items() if isinstance(v, dict) and v.get("type") == "meta_command"]
            if text_commands:
                latest = max(text_commands, key=lambda x: x.get("timestamp", 0))
                thought = latest.get("thought", "").lower()

                if "increase exploration" in thought or "raise exploration" in thought:
                    old_rate = getattr(self.engine, '_mutation_rate', 0.25)
                    new_rate = min(0.7, old_rate * 1.2)
                    if hasattr(self.engine, 'set_mutation_rate'):
                        self.engine.set_mutation_rate(new_rate)
                    logger.info(f"🧠 MetaAgent: exploration {old_rate:.2f} → {new_rate:.2f}")

                if "tighten stop-loss" in thought or "tighten stop loss" in thought:
                    old_sl = self.current_params.get("stop_loss_ratio", 0.05)
                    new_sl = max(0.001, old_sl * 0.8)
                    self.current_params["stop_loss_ratio"] = new_sl
                    logger.info(f"🧠 MetaAgent: stop-loss {old_sl:.4f} → {new_sl:.4f}")

                if "convert excess usdc" in thought or "convert usdc" in thought:
                    from swarm_config import config
                    old_max = config.trading.max_usdc_balance
                    config.trading.max_usdc_balance = max(50.0, old_max * 0.8)
                    logger.info(f"🧠 MetaAgent: USDC max {old_max:.2f} → {config.trading.max_usdc_balance:.2f}")

                if "reduce risk" in thought or "lower risk" in thought:
                    old_risk = self.current_params.get("max_risk_per_trade", 0.05)
                    new_risk = max(0.001, old_risk * 0.8)
                    self.current_params["max_risk_per_trade"] = new_risk
                    logger.info(f"🧠 MetaAgent: risk {old_risk:.4f} → {new_risk:.4f}")

                if "increase phi" in thought or "raise phi" in thought:
                    old_phi = self.current_params.get("phi_llm", 0.15)
                    new_phi = min(1.0, old_phi * 1.2)
                    self.current_params["phi_llm"] = new_phi
                    logger.info(f"🧠 MetaAgent: phi_llm {old_phi:.4f} → {new_phi:.4f}")

                if "decrease volatility" in thought or "lower volatility threshold" in thought:
                    old_vol = self.current_params.get("volatility_threshold", 0.02)
                    new_vol = max(0.001, old_vol * 0.8)
                    self.current_params["volatility_threshold"] = new_vol
                    logger.info(f"🧠 MetaAgent: volatility threshold {old_vol:.4f} → {new_vol:.4f}")

        except Exception as e:
            logger.debug(f"Meta command processing skipped: {e}")

    async def _evolution_cycle(self):
        """Фоновый цикл эволюции (генетика, LLM-мутации)."""
        while True:
            try:
                await self._tick_evolution()
            except Exception as e:
                logger.error(f"Evolution cycle error: {e}")
            await asyncio.sleep(0.5)

    async def _sync_cycle(self):
        """Фоновый цикл синхронизации с роем (gossip, импорт геномов)."""
        while True:
            try:
                await self._sync_swarm()
            except Exception as e:
                logger.error(f"Sync cycle error: {e}")
            await asyncio.sleep(0.5)

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def node_niche(self) -> str:
        if self.survival.dq >= 0.8 or self.survival.liveness < 0.5:
            return "survival"
        if self.capital > 50000 and self.survival.dq < 0.3:
            return "capital"
        return "exploration"

    def accept_genome(self, genome: dict) -> bool:
        if genome.get("fitness", 0) < 0.001:
            return False
        for v in genome.get("params", {}).values():
            if not (0 < v < 10):
                return False
        pubkey = genome.get("origin_pubkey")
        if pubkey and not self.reputation.is_trusted(pubkey):
            return False
        return True

    def make_genome(self, params: Dict[str, float], fitness: float) -> dict:
        return {
            "params": params,
            "fitness": fitness,
            "niche": self.node_niche(),
            "origin": self.node_id,
            "lineage": [self.node_id],
            "ts": time.time(),
        }

    def dict_to_genome(self, d: dict, niche: str = "exploration") -> Genome:
        return Genome(
            params={str(k): float(v) for k, v in d.get("params", d).items() if isinstance(v, (int, float))},
            fitness=float(d.get("fitness", 0.0)),
            niche=str(d.get("niche", niche)),
            lineage=list(d.get("lineage", [])[:12]),
        )

    def local_score(self, genome: Genome) -> float:
        base = genome.fitness
        bias = 1.0
        if genome.niche == "survival":
            bias += min(0.5, self.survival.liveness)
        elif genome.niche == "exploration":
            bias += min(0.3, self.curiosity.surprise_threshold)
        elif genome.niche == "capital":
            bias += min(0.5, self.capital / 2000)

        if len(self.memory) > 0:
            vol = self._current_volatility()
            similar = self.memory.find_similar(vol, self.survival.dq, top_k=5)
            for rec in similar:
                if rec["params"] == genome.params:
                    bias += 0.2
                    break
        return base * bias

    def population_diversity(self) -> float:
        pop = self.engine.population
        if not pop:
            return 0.0
        sigs = {hashlib.md5(str(sorted(g.params.items())).encode()).hexdigest() for g in pop if isinstance(g, Genome)}
        return len(sigs) / len(pop) if pop else 0.0

    def population_niche_counts(self) -> Dict[str, int]:
        counts = {"survival": 0, "capital": 0, "exploration": 0}
        for g in self.engine.population:
            if isinstance(g, Genome):
                niche = g.niche
            elif isinstance(g, dict):
                niche = g.get("niche", "exploration")
            else:
                continue
            counts[niche] = counts.get(niche, 0) + 1
        return counts

    def _current_volatility(self) -> float:
        prev = getattr(self, '_prev_price', 100.0)
        prev_prev = getattr(self, '_prev_prev_price', 100.0)
        return abs(prev - prev_prev) / max(1.0, prev)

    def _seed_from_memory(self) -> None:
        if len(self.memory) == 0:
            return
        current_volatility = self._current_volatility()
        similar = self.memory.find_similar(current_volatility, self.survival.dq, top_k=3)
        for rec in similar:
            try:
                genome = self.dict_to_genome({"params": rec["params"]})
                self.engine.add_genome(genome)
            except Exception as e:
                logger.debug(f"Seed from memory skipped: {e}")

    # ------------------------------------------------------------
    # Market
    # ------------------------------------------------------------
    async def get_market_tick(self, session: aiohttp.ClientSession, symbol: str = "BTC/USDT") -> dict:
        if self.market_mode == "live" and self.market_adapter:
            adapter = self.market_adapter.get_adapter(symbol)
            if adapter:
                tick = await adapter.get_ticker()
                if tick is not None:
                    scale = config.trading.price_scale
                    tick['price'] = tick.get('price', tick.get('ask', 50000))
                    tick['price'] = tick['price'] / scale
                    return tick
        if self.market_url:
            try:
                async with session.get(self.market_url, timeout=1) as resp:
                    return await resp.json()
            except Exception as e:
                logger.debug(f"Market URL request failed: {e}")
        return {"price": random.uniform(90, 110)}

    # ------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------
    async def main_loop(self) -> None:
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
                        fitness=self.engine.champion[1] if hasattr(self.engine, 'champion') and self.engine.champion else 0.0,
                        diversity=self.engine.diversity(),
                        crdt_size=len(self.crdt.state),
                        trace_id=self._trace_id,
                    )
                    logger.info(f"[{self.node_id}] failed")
                    sys.exit(1)

                # 1. Рынок
                best_symbol, best_market, snapshot = await self._collect_market_snapshot(session)

                # 2. Авто-конвертация и стоп-лосс
                if self.market_mode == "web3":
                    adapter = self.market_adapter.get_adapter(best_symbol)
                    if adapter:
                        block_number = await adapter.w3.eth.block_number
                        if self.is_leader(block_number):
                            await self.trading_controller.check_and_rebalance(adapter)

                if self.market_mode == "futures":
                    adapter = self.market_adapter.get_adapter(best_symbol)
                    if adapter and hasattr(adapter, 'check_stop_loss'):
                        try:
                            positions = adapter.exchange.fetch_positions([best_symbol])
                            if positions and len(positions) > 0:
                                pos = positions[0]
                                if float(pos['contracts']) > 0:
                                    entry_price = float(pos['entryPrice'])
                                    current_price = best_market['price']
                                    side = 'long' if pos['side'] == 'long' else 'short'
                                    if adapter.check_stop_loss(entry_price, current_price, side):
                                        logger.info(f"Stop‑loss triggered for {best_symbol}")
                                        adapter.close_position(best_symbol)
                                        await self.telegram_notifier.send(
                                            f"🛑 <b>Stop‑loss triggered</b>\n"
                                            f"Node: {self.node_id}\n"
                                            f"Symbol: {best_symbol}\n"
                                            f"Capital: {self.capital:.2f}"
                                        )
                                        if self.market_adapter.hedge_enabled:
                                            spot_adapter = self.market_adapter.get_adapter(best_symbol, "spot")
                                            if spot_adapter:
                                                try:
                                                    spot_adapter.close_position(best_symbol)
                                                except Exception as e:
                                                    logger.warning(f"Hedge close failed: {e}")
                        except Exception as e:
                            logger.warning(f"Futures stop-loss check failed: {e}")

                # 3. Burn
                self.capital_manager.burn()
                self.capital = self.capital_manager.capital
                if not self.capital_manager.is_alive():
                    logger.info(f"[{self.node_id}] died")
                    return

                # 4. Survival + Trade
                await self._evaluate_survival_and_trade(best_market, best_symbol)

                self._last_market = best_market

                # 7. Периодические задачи
                await self._periodic_tasks()

                # 8. Проверка низкого капитала
                self.telemetry.update_impact(self.capital)
                alert_threshold = config.capital_alert_threshold
                if self.capital < alert_threshold:
                    await self.telemetry.low_capital_alert(self.capital, alert_threshold)

                await asyncio.sleep(0.5)

    def _recombine(self, g1: dict, g2: dict) -> dict:
        all_keys = set(g1.get("params", {}).keys()) | set(g2.get("params", {}).keys())
        child = {}
        for k in all_keys:
            v1 = g1.get("params", {}).get(k, 0.5)
            v2 = g2.get("params", {}).get(k, 0.5)
            val = v1 if random.random() < 0.5 else v2
            if random.random() < 0.1:
                val *= random.uniform(0.9, 1.1)
            val = max(0.0001, min(1.0, val))
            child[k] = val
        return {
            "params": child,
            "fitness": 0.0,
            "niche": g1.get("niche", "mixed") if random.random() < 0.5 else g2.get("niche", "mixed"),
            "lineage": (g1.get("lineage", [])[-5:] + [self.node_id]),
            "ts": time.time(),
        }

    async def _collect_market_snapshot(self, session):
        snapshot = await self.market_service.get_snapshot(session)
        best_symbol, best_market = select_best_market(snapshot)
        return best_symbol, best_market, snapshot

    async def _evaluate_survival_and_trade(self, market, symbol):
        expected = market["price"] * EXPECTED_RETURN_RATE
        _, approved = self.survival.evaluate_trade(self.capital, expected)
        logger.info(f"[{self.node_id}] Survival approved={approved}, capital={self.capital:.2f}, expected={expected:.4f}")
        if not approved:
            return None

        fraction, _ = self.dispatcher.evaluate(market, self.capital)
        if fraction <= 0:
            return None

        side = config.trading.test_web3_swap_side
        test_amount = config.trading.test_web3_swap_amount

        trade_result = await self.executor.execute_order(
            symbol=symbol,
            side=side,
            amount=test_amount,
            price=market.get("price", 0),
            capital=self.capital,
        )

        ret = market["price"] * fraction * 0.1
        prev_capital = self.capital
        self.capital *= (1 + ret)
        self.capital -= 1.0
        self.capital_manager.capital = self.capital
        self.capital_manager.apply_dq_delta(0.001)

        if trade_result and trade_result.get("success"):
            trade_logger.info(f"TRADE | {symbol} | {side} | status: {trade_result.get('status')}")
            self.telemetry.update_impact(self.capital)

        if self.market_mode == "futures" and self.market_adapter.hedge_enabled:
            hedge_ratio = config.hedge_ratio
            spot_adapter = self.market_adapter.get_adapter(symbol, "spot")
            futures_adapter = self.market_adapter.get_adapter(symbol, "futures")
            if spot_adapter and futures_adapter:
                side_hedge = 'sell' if fraction > 0 else 'buy'
                hedge_amount = abs(fraction) * hedge_ratio * self.capital / market['price']
                try:
                    spot_adapter.place_order(side_hedge, hedge_amount)
                    logger.info(f"Hedge order placed: {side_hedge} {hedge_amount} {symbol}")
                except Exception as e:
                    logger.error(f"Hedge order failed: {e}")

        if trade_result and isinstance(trade_result, dict):
            await self.telemetry.trade(
                step=self.step_count,
                symbol=symbol,
                side=side,
                amount=test_amount,
                tx_hash=trade_result.get("tx_hash", ""),
                status=trade_result.get("status", "unknown"),
                capital_before=prev_capital,
                capital_after=self.capital,
                trace_id=self._trace_id,
            )

        return trade_result

    async def _tick_evolution(self):
        await self.evolution_engine.tick(self._last_market)

    async def _sync_swarm(self):
        await self.swarm_sync.reconcile()

    async def _periodic_tasks(self):
        if self.step_count % 50 == 0:
            await self._apply_meta_commands()

        if self.step_count % 30 == 0:
            try:
                self.telemetry.heartbeat(
                    step=self.step_count,
                    capital=self.capital,
                    dq=self.survival.dq,
                    fitness=self.engine.champion[1] if hasattr(self.engine, 'champion') and self.engine.champion else 0.0,
                    diversity=self.population_diversity(),
                    crdt_size=len(self.crdt.state),
                    llm_mutations=_llm_mutation_count,
                    niche_counts=self.population_niche_counts(),
                    trace_id=self._trace_id,
                )

                # Дублируем heartbeat в CRDT для MetaAgent
                heartbeat_payload = {
                    "type": "heartbeat",
                    "capital": self.capital,
                    "dq": self.survival.dq,
                    "fitness": self.engine.champion[1] if hasattr(self.engine, 'champion') and self.engine.champion else 0.0,
                    "diversity": self.population_diversity(),
                    "crdt_size": len(self.crdt.state),
                    "llm_mutations": _llm_mutation_count,
                    "niche_counts": self.population_niche_counts(),
                    "node_id": self.node_id,
                    "timestamp": time.time(),
                }
                await self.crdt.add_genome(heartbeat_payload)
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
                
        if self.step_count % 500 == 0:
            self.memory.records = list({
                (rec["params"].get("max_risk_per_trade", 0), rec["params"].get("phi_llm", 0)): rec
                for rec in self.memory.records
            }.values())
            if len(self.memory.records) > self.memory.max_size:
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

        if self.step_count % 200 == 0:
            self.semantic.derive_rules(self.memory.to_dict_list())
            await self.crdt.prune()
            top = await self.crdt.get_top(20)
            if top:
                sample = random.choice(top)
                pubkey = sample.get("origin_pubkey")
                if pubkey and pubkey != self.crypto.public_bytes_hex:
                    actual_fit = self.engine._fitness(sample["params"])
                    claimed_fit = sample.get("fitness", 0.0)
                    self.reputation.update(pubkey, claimed_fit, actual_fit)

            if self.memory_api_enabled:
                stats = await self.memory_api.compress()
                logger.info(f"Memory stats: {stats}")

    async def start(self) -> None:
        logger.info(f"[{self.node_id}] port={self.port} peers={self.peers}")

        loop = asyncio.get_running_loop()
        shutdown_event = asyncio.Event()

        if self.tradingview_enabled:
            await self.tradingview_webhook.start()

        def _shutdown():
            logger.info(f"[{self.node_id}] received signal, shutting down gracefully")
            shutdown_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _shutdown)
            except NotImplementedError:
                pass

        async def _shutdown_waiter():
            await shutdown_event.wait()
            if self.memory_api_enabled:
                await self.memory_api.save_to_db()
                logger.info(f"[{self.node_id}] memory saved before exit")
            raise SystemExit(0)

        if self.tradingview_enabled:
            await self.tradingview_webhook.stop()

        if self.market_mode == "web3":
            for sym in self.symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter and hasattr(adapter, 'initialize'):
                    logger.info(f"Initializing web3 adapter for {sym} ...")
                    await adapter.initialize()
                if adapter:
                    self.nonce_manager = adapter.nonce_manager
                    self.mutation_engine.nonce_manager = self.nonce_manager

            adapter = self.market_adapter.get_adapter(self.symbols_list[0]) if self.symbols_list else None
            self.executor = build_backend(self.node_id, adapter, self.is_leader)

        self._evolution_task = asyncio.create_task(self._evolution_cycle())
        self._sync_task = asyncio.create_task(self._sync_cycle())

        await asyncio.gather(
            self.gossip.start(),
            self._evolution_task,
            self._sync_task,
            self.main_loop(),
            _shutdown_waiter(),
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    node = SwarmNode()
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        logger.info("Node stopped.")
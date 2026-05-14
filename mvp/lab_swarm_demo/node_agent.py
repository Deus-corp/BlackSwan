import os, time, random, uuid, hashlib, asyncio, logging, sys, signal, json, socket
from typing import Dict, Any, Optional, List, Tuple

import aiohttp
from aiohttp import web

from src.economy.roi_dispatcher import ROIDispatcher
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
from src.security.gossip_envelope import sign_envelope, generate_key_pair, public_key_bytes, sha256, GossipEnvelope
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from src.memory.local_memory import LocalMemoryAPI, MemoryRecord
from adapters.live_market import BinanceTestnetAdapter
from src.core.events import Event
from src.core.event_store import EventStore
from src.security.key_manager import KeyManager
from adapters.multi_pair_adapter import MultiPairAdapter
from adapters.web3_testnet import WETH_ADDRESS, USDC_ADDRESS
from src.intelligence.internet_researcher import InternetResearcher
from adapters.tradingview_webhook import TradingViewWebhook
from adapters.orderbook_analyzer import OrderBookAnalyzer
from src.observability.telegram_notifier import TelegramNotifier
from src.intelligence.strategy_schema import StrategyParams
from swarm_config import config
from src.core.trading_controller import TradingController
from src.evolution.mutation_engine import MutationEngine
from prometheus_client import Counter, Gauge
from mvp.lab_swarm_demo.leader import select_leader
from mvp.lab_swarm_demo.execution import build_backend
from mvp.lab_swarm_demo.market import MarketSnapshotService, select_best_market
from mvp.lab_swarm_demo.capital_manager import CapitalManager

import logging
logger = logging.getLogger("SwarmNode")
trade_logger = logging.getLogger("SwarmNode.Trade")
# Уровень устанавливается из переменной окружения LOG_LEVEL (по умолчанию INFO)
logging.basicConfig(level=config.log_level)

EXPECTED_RETURN_RATE = config.expected_return_rate
MAX_NORMALIZED_CAPITAL = config.max_normalized_capital

# LLM mutation counters (глобально, т.к. в каждом процессе они независимы)
_llm_mutation_count = 0
_llm_mutation_total_impact = 0.0
_last_capital = None          # запоминаем предыдущий капитал для расчёта impact

mutation_counter = Counter('swarm_mutations_total', 'Total number of LLM mutations')
mutation_impact_gauge = Gauge('swarm_mutation_impact', 'Average impact of mutations on capital')

def note_llm_mutation():
    global _llm_mutation_count
    _llm_mutation_count += 1
    mutation_counter.inc()

def update_llm_impact(current_capital: float):
    global _llm_mutation_total_impact, _last_capital
    if _last_capital is not None:
        impact = current_capital - _last_capital
        _llm_mutation_total_impact += impact
    _last_capital = current_capital
    # Обновляем средний impact (можно обновлять не каждый раз, а при чтении, но так проще)
    avg = _llm_mutation_total_impact / _llm_mutation_count if _llm_mutation_count else 0.0
    mutation_impact_gauge.set(avg)

def get_llm_stats() -> Tuple[int, float]:
    avg = _llm_mutation_total_impact / _llm_mutation_count if _llm_mutation_count else 0.0
    return _llm_mutation_count, avg

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

        # ========== INFRASTRUCTURE LAYER (BODY) ==========
        # Криптография и безопасность
        self.key_manager = KeyManager()
        self.crypto: CryptoManager = CryptoManager()

        # Сеть и Gossip
        self.reputation: ReputationManager = ReputationManager()
        self.reputation_blacklist_threshold: float = 0.3

        self.memory_api_enabled: bool = config.memory_api_enabled
        self.memory_api: LocalMemoryAPI = LocalMemoryAPI(
            node_id=self.node_id,
            storage=None  # будет подключён после создания CRDT
        )

        self.internet_researcher: InternetResearcher = InternetResearcher(
            memory_api=self.memory_api if self.memory_api_enabled else None
        )
                # Telegram уведомления
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

        # Хранилище событий (всегда, независимо от флагов)
        self.event_store = EventStore(
            ledger_path=config.event_ledger_path,
            sqlite_path=config.event_sqlite_path,
        )

        # Рыночные данные – теперь мульти-парный адаптер
        trading_symbols = config.trading_symbols
        symbols_list = [s.strip() for s in trading_symbols.split(",") if s.strip()]
        self.symbols_list = symbols_list   # сохраняем для использования в start()
        self.market_adapter = MultiPairAdapter(
            symbols=symbols_list,
            market_mode=self.market_mode,
            crdt_adapter=self.crdt if self.market_mode == "web3" else None
        )
                # Market layer (PR-4)
        self.market_service = MarketSnapshotService(
            market_adapter=self.market_adapter,
            market_mode=self.market_mode,
        )
        # --- принудительно прокидываем CRDT в web3 адаптер ---
        if self.market_mode == "web3":
            for sym in symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter and hasattr(adapter, 'crdt'):
                    adapter.crdt = self.crdt

        self.primary_symbol = symbols_list[0] if symbols_list else "BTC/USDT"

                # TradingView webhook (если включен)
        self.tradingview_enabled = config.tradingview_webhook_enabled
        self.tradingview_webhook = None
        if self.tradingview_enabled:
            self.tradingview_webhook = TradingViewWebhook(port=config.tradingview_webhook_port)

                # OrderBook анализ (если включён)
        self.orderbook_enabled = config.orderbook_analysis_enabled
        self.orderbook_analyzers: Dict[str, OrderBookAnalyzer] = {}
        if self.orderbook_enabled:
            for sym in symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter:
                    self.orderbook_analyzers[sym] = OrderBookAnalyzer(adapter)

        # ========== INTELLIGENCE LAYER (BRAIN) ==========
        # Генетический движок и стратегии
        self.engine: GeneticEngine = GeneticEngine(pop_size=10)
        self.engine.initialize()

        self.state: GlobalState = GlobalState()
        best = self.state.get_best_genomes(top_n=1)
        self.current_params: Dict[str, float] = list(best.values())[-1] if best else {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
        self.dispatcher: ROIDispatcher = ROIDispatcher(config=self.current_params)

        # Оценка выживания и мотивация
        self.survival: SurvivalEvaluator = SurvivalEvaluator()
        self.survival.dq = 0.03
        self.survival.liveness = 1.0
        
        self.curiosity: CuriosityEngine = CuriosityEngine(window_size=10, surprise_threshold=0.3)
        self.meta_agent: MetaPOMDPAgent = MetaPOMDPAgent()
        self.llm = LLMClient()

        # Память (эпизодическая/семантическая) — старая, но пока оставляем
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
        self.nonce_manager = None   # будет инициализирован после создания адаптера
        
                # Capital & Risk Manager (PR-5)
        self.capital_manager = CapitalManager(capital=self.capital)
        self.capital_manager.set_survival(self.survival)

                # Execution backend (PR-3)
        self.executor = build_backend(
            node_id=self.node_id,
            adapter=None,   # будет передан позже, когда адаптер готов (для web3)
            is_leader_func=self.is_leader,
        )

    def is_leader(self, block_number: int) -> bool:
        leader_index = select_leader(self.node_id, block_number, config.total_nodes)
        return self.node_index == leader_index

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
        #sig = genome.get("signature")
        #pubkey = genome.get("origin_pubkey")
        #if sig and pubkey:
            #payload = {"params": genome.get("params", {}), "fitness": genome.get("fitness", 0.0)}
            #if not CryptoManager.verify(payload, sig, pubkey):
                #return False
        # репутационный фильтр
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
            except Exception:
                pass

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
        # fallback – симуляция
        if self.market_url:
            try:
                async with session.get(self.market_url, timeout=1) as resp:
                    return await resp.json()
            except Exception:
                pass
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
                    self.event_store.append(Event.create(
                        node_id=self.node_id,
                        event_type="spore_failure",
                        payload={
                            "step": self.step_count,
                            "capital": self.capital,
                            "dq": self.survival.dq,
                            "fitness": self.engine.champion[1],
                            "diversity": self.engine.diversity(),
                            "crdt_size": len(self.crdt.state),
                            "trace_id": self._trace_id,
                        },
                        parent_id=self._trace_id,
                    ))
                    logger.info(f"[{self.node_id}] failed")
                    sys.exit(1)

                # Получаем снапшот рынка и выбираем лучший символ
                snapshot = await self.market_service.get_snapshot(session)
                best_symbol, best_market = select_best_market(snapshot)

                # Авто-конвертация USDC/WETH/ETH (выполняет только лидер)
                if self.market_mode == "web3":
                    adapter = self.market_adapter.get_adapter(best_symbol)
                    if adapter:
                        block_number = await adapter.w3.eth.block_number
                        if self.is_leader(block_number):
                            await self.trading_controller.check_and_rebalance(adapter)

                # Проверка стоп‑лосса для фьючерсных позиций
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
                                                    logger.info("Hedge position closed")
                                                except:
                                                    pass
                        except Exception:
                            pass
                
                market = best_market
                self.capital_manager.burn()
                self.capital = self.capital_manager.capital   # синхронизируем
                if not self.capital_manager.is_alive():
                    logger.info(f"[{self.node_id}] died")
                    return

                # -- получаем ордербук для выбранного инструмента --
                ob_imbalance = 0.0
                ob_delta_volume = 0.0
                if self.orderbook_enabled and best_symbol in self.orderbook_analyzers:
                    analyzer = self.orderbook_analyzers[best_symbol]
                    metrics = await analyzer.update()  # обновим и получим словарь
                    if metrics:
                        ob_imbalance = metrics.get("imbalance", 0.0)
                        ob_delta_volume = metrics.get("delta_volume", 0.0)

                # -- расширенный контекст для мутации (обновляется редко, но можно хранить последний) --
                self._last_orderbook_context = {
                    "imbalance": ob_imbalance,
                    "delta_volume": ob_delta_volume,
                    "symbol": best_symbol
                }

                action = self.trading_controller.decide_action(
                    market=market,
                    current_params=self.current_params,
                    capital=self.capital,
                    step=self.step_count,
                    orderbook_imbalance=ob_imbalance,
                    orderbook_delta_volume=ob_delta_volume
                )

                expected = market["price"] * EXPECTED_RETURN_RATE
                #_, approved = self.survival.evaluate_trade(self.capital, expected)
                approved = True   # временно, пока не настроим пороги
                logger.info(f"[{self.node_id}] Survival approved={approved}, capital={self.capital:.2f}, expected={expected:.4f}")
                logger.debug(f"Survival check: expected={expected:.4f} approved={approved}")
                if approved:
                    fraction, _ = self.dispatcher.evaluate(market, self.capital)
                    if fraction > 0:
                        side = config.trading.test_web3_swap_side
                        test_amount = config.trading.test_web3_swap_amount

                        # --- Исполнение через ExecutionBackend (PR-3) ---
                        trade_result = await self.executor.execute_order(
                            symbol=best_symbol,
                            side=side,
                            amount=test_amount,
                            price=market.get("price", 0),
                            capital=self.capital,
                        )

                        # Обновление капитала по симуляционной формуле (как раньше)
                        ret = market["price"] * fraction * 0.1
                        prev_capital = self.capital
                        self.capital *= (1 + ret)
                        self.capital_manager.capital = self.capital   # синхронизируем с менеджером
                        self.capital -= 1.0
                        self.capital_manager.apply_dq_delta(0.001)

                        if trade_result and trade_result.get("success"):
                            trade_logger.info(
                                f"TRADE | {best_symbol} | {side} | "
                                f"status: {trade_result.get('status')}"
                            )
                            update_llm_impact(self.capital)

                        logger.debug(
                            f"[{self.node_id}] TRADE | step={self.step_count} "
                            f"symbol={best_symbol} price={market['price']:.2f} fraction={fraction:.4f} "
                            f"ret={ret:.6f} capital_before={prev_capital:.2f} "
                            f"capital_after={self.capital:.2f} dq={self.survival.dq:.3f} "
                            f"params={self.current_params}"
                        )

                        # Хеджирование (только для futures)
                        if self.market_mode == "futures" and self.market_adapter.hedge_enabled:
                            hedge_ratio = config.hedge_ratio
                            spot_adapter = self.market_adapter.get_adapter(best_symbol, "spot")
                            futures_adapter = self.market_adapter.get_adapter(best_symbol, "futures")
                            if spot_adapter and futures_adapter:
                                side = 'sell' if fraction > 0 else 'buy'
                                hedge_amount = abs(fraction) * hedge_ratio * self.capital / market['price']
                                try:
                                    spot_adapter.place_order(side, hedge_amount)
                                    logger.info(f"Hedge order placed: {side} {hedge_amount} {best_symbol}")
                                except Exception as e:
                                    logger.error(f"Hedge order failed: {e}")

                        # Запись события сделки
                        if trade_result and isinstance(trade_result, dict):
                            self.event_store.append(Event.create(
                                node_id=self.node_id,
                                event_type="trade_executed",
                                payload={
                                    "step": self.step_count,
                                    "symbol": best_symbol,
                                    "side": side,
                                    "amount": test_amount,
                                    "tx_hash": trade_result.get("tx_hash", ""),
                                    "status": trade_result.get("status", "unknown"),
                                    "capital_before": prev_capital,
                                    "capital_after": self.capital,
                                    "trace_id": self._trace_id,
                                },
                                parent_id=self._trace_id,
                            ))

                        await self.telegram_notifier.send(
                            f"🦢 <b>Trade</b>\n"
                            f"Node: {self.node_id}\n"
                            f"Step: {self.step_count}\n"
                            f"Symbol: {best_symbol}\n"
                            f"Price: {market['price']:.2f}\n"
                            f"Capital: {self.capital:.2f}"
                        )

                # ---- import genomes ----
                if self.step_count - self.last_import_step > self.import_cooldown:
                    remote = await self.crdt.get_top(10)
                    remote_genomes = []
                    for g in remote:
                        if self.accept_genome(g):
                            try:
                                remote_genomes.append(self.dict_to_genome(g))
                            except Exception:
                                pass
                    scored = sorted(remote_genomes, key=self.local_score, reverse=True)
                    pref = self.node_niche()
                    counts = self.population_niche_counts()
                    total = sum(counts.values()) or 1
                    selected = []
                    for g in scored:
                        niche = g.niche
                        share = counts.get(niche, 0) / total
                        prob = 0.2
                        if niche == pref:
                            prob = 1.0
                        elif share > 0.5:
                            prob = 0.3
                        if random.random() < prob:
                            selected.append(g)
                        if len(selected) >= self.max_import:
                            break
                    for g in selected:
                        if self.engine.population:
                            parent_obj = random.choice(self.engine.population)
                            if isinstance(parent_obj, Genome):
                                parent_dict = {
                                    "params": parent_obj.params,
                                    "fitness": parent_obj.fitness,
                                    "niche": parent_obj.niche,
                                    "lineage": parent_obj.lineage,
                                }
                            else:
                                parent_dict = parent_obj
                        else:
                            continue
                        child_dict = self._recombine(
                            parent_dict,
                            {"params": g.params, "fitness": g.fitness, "niche": g.niche, "lineage": g.lineage},
                        )
                        child_genome = self.dict_to_genome(child_dict, niche=g.niche)
                        self.engine.add_genome(child_genome)
                        self.event_store.append(Event.create(
                            node_id=self.node_id,
                            event_type="genome_imported",
                            payload={
                                "step": self.step_count,
                                "gid": child_genome.params,
                                "fitness": child_genome.fitness,
                                "niche": child_genome.niche,
                                "origin": g.params if hasattr(g, 'params') else str(g),
                                "trace_id": self._trace_id,
                            },
                            parent_id=self._trace_id,
                        ))
                    self.last_import_step = self.step_count

                # ---- evolution ----
                if self.step_count % 50 == 0:
                    self.engine.evolve_generation()
                    if self.engine.champion[1] > 0:
                        current_vol = self._current_volatility()
                        params_to_publish = self.semantic.apply_rules(
                            self.engine.champion[0], current_vol, self.survival.dq
                        )
                        genome_dict = self.make_genome(params_to_publish, self.engine.champion[1])

                        if config.gossip_signing_enabled:
                            self.gossip_seq_no += 1
                            self.gossip_lamport_ts += 1
                            meta = {
                                "envelope_version": "1.0",
                                "domain": "blackswan-gossip-v1",
                                "payload_type": "memory.fact",
                                "topic": "swarm.genome",
                                "sender_peer_id": self.node_id,
                                "sender_node_id": self.node_id,
                                "sender_pubkey": self.gossip_public_bytes,
                                "key_id": self.gossip_key_id,
                                "key_version": 1,
                                "seq_no": self.gossip_seq_no,
                                "lamport_ts": self.gossip_lamport_ts,
                                "nonce": os.urandom(16).hex(),
                                "timestamp_ms": int(time.time() * 1000),
                                "ttl_ms": 60000,
                                "expires_at_ms": int(time.time() * 1000) + 60000,
                                "parent_hashes": [],
                            }
                            envelope = sign_envelope(genome_dict, meta, self.gossip_private_key)
                            await self.crdt.add_genome(envelope.model_dump(mode='json'))
                        else:
                            payload = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]}
                            genome_dict["signature"] = self.crypto.sign(payload)
                            genome_dict["origin_pubkey"] = self.crypto.public_bytes_hex
                            await self.crdt.add_genome(genome_dict)

                    if self.step_count % 100 == 0:
                        external_context = ""
                        if config.internet_researcher_enabled:
                            try:
                                external_context = await self.internet_researcher.gather_context()
                            except Exception:
                                external_context = ""

                        if self.tradingview_enabled and self.tradingview_webhook.latest_signal:
                            signal = self.tradingview_webhook.latest_signal
                            external_context += f"\nTradingView signal: {signal}\n"

                        if self.orderbook_enabled:
                            for sym, analyzer in self.orderbook_analyzers.items():
                                metrics = await analyzer.update()
                                if metrics:
                                    external_context += f"\n{sym} OrderBook: {analyzer.get_context_string()}"

                        context = (
                            f"volatility={self._current_volatility():.3f}, "
                            f"dq={self.survival.dq:.3f}, "
                            f"capital={self.capital:.2f}"
                        )
                        if external_context:
                            context += "\n" + external_context

                        # --- Memory replay: добавляем похожие успешные эпизоды ---
                        if len(self.memory) > 0:
                            vol = self._current_volatility()
                            similar = self.memory.find_similar(vol, self.survival.dq, top_k=3)
                            if similar:
                                memory_lines = ["Past successful strategies in similar conditions:"]
                                for i, rec in enumerate(similar):
                                    params = rec.get("params", {})
                                    fitness = rec.get("fitness", 0.0)
                                    memory_lines.append(f"{i+1}. params={params}, fitness={fitness:.4f}")
                                memory_context = "\n".join(memory_lines)
                                context += "\n" + memory_context
                        # --------------------------------------------------------

                        new_params = self.mutation_engine.mutate(self.engine.champion[0], context)
                        if new_params != self.engine.champion[0]:
                            genome = self.dict_to_genome({"params": new_params})
                            self.engine.add_genome(genome)
                            note_llm_mutation()

                    if self.engine.champion[1] > self.engine._fitness(self.current_params):
                        self.current_params = self.engine.champion[0]
                        self.dispatcher = ROIDispatcher(config=self.current_params)

                    self._prev_prev_price = self._prev_price
                    self._prev_price = market.get("price", self._prev_price)

                    if self.engine.champion[1] > 0:
                        self.memory.add(
                            market_volatility=self._current_volatility(),
                            dq=self.survival.dq,
                            capital=self.capital,
                            params=self.engine.champion[0],
                            fitness=self.engine.champion[1],
                        )

                    cur_niche = self.node_niche()
                    counts = self.population_niche_counts()
                    dom_niche = max(counts, key=counts.get)
                    llm_muts, avg_impact = get_llm_stats()
                    logger.info(
                        f"[{self.node_id}] step={self.step_count} capital={self.capital:.2f} "
                        f"dq={self.survival.dq:.3f} fitness={self.engine.champion[1]:.4f} "
                        f"diversity={self.engine.diversity():.2f} crdt_size={len(self.crdt.state)} "
                        f"niche={cur_niche} dominant={dom_niche} "
                        f"llm_muts={llm_muts} avg_llm_impact={avg_impact:+.2f}"
                    )

                    if self.memory_api_enabled:
                        record = MemoryRecord(
                            id="",
                            kind="summary",
                            scope="local",
                            payload={
                                "step": self.step_count,
                                "capital": self.capital,
                                "fitness": self.engine.champion[1],
                                "diversity": self.engine.diversity(),
                                "crdt_size": len(self.crdt.state),
                                "niche": cur_niche,
                                "dominant": dom_niche,
                                "llm_muts": llm_muts,
                                "avg_llm_impact": avg_impact
                            },
                            confidence=0.9,
                            priority=10
                        )
                        await self.memory_api.remember(record)

                # ---- curiosity + meta ----
                if self.step_count % 100 == 0:
                    if self.market_mode == "futures":
                        vol = self._current_volatility()
                        for sym in self.market_adapter.symbols:
                            adapter = self.market_adapter.get_adapter(sym)
                            if adapter and hasattr(adapter, 'adjust_leverage'):
                                await adapter.adjust_leverage(vol)

                    hypothesis = self.curiosity.update(market)
                    if hypothesis:
                        self.engine.add_genome(self.dict_to_genome(hypothesis))
                    norm_cap = min(1.0, self.capital / MAX_NORMALIZED_CAPITAL)
                    surprise = self.curiosity.prediction_errors[-1] if self.curiosity.prediction_errors else 0.0
                    weights = self.meta_agent.update(
                        dq=self.survival.dq,
                        liveness=self.survival.liveness,
                        capital=norm_cap,
                        surprise=surprise,
                    )
                    self.survival.config["lambda"] = weights["w_capital"]
                    if self.meta_agent.current_scenario in ("crisis", "stealth_mode"):
                        self.engine.set_mutation_rate(0.1)
                    elif self.meta_agent.current_scenario == "exploration":
                        self.engine.set_mutation_rate(0.5)
                    else:
                        self.engine.set_mutation_rate(0.25)

                # ---- prune + semantic update + spot-check ----
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

                # ---- memory consolidation ----
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

                update_llm_impact(self.capital)
                alert_threshold = config.capital_alert_threshold
                if self.capital < alert_threshold:
                    await self.telegram_notifier.send(
                        f"⚠️ <b>Low capital alert</b>\n"
                        f"Node: {self.node_id}\n"
                        f"Step: {self.step_count}\n"
                        f"Capital: {self.capital:.2f} (threshold: {alert_threshold})"
                    )

                await asyncio.sleep(0.5)

        # Быстрый фикс _recombine — убираем @staticmethod, чтобы self был доступен
    def _recombine(self, g1: dict, g2: dict) -> dict:
        # объединяем все ключи из обоих родителей
        all_keys = set(g1.get("params", {}).keys()) | set(g2.get("params", {}).keys())
        child = {}
        for k in all_keys:
            v1 = g1.get("params", {}).get(k, 0.5)      # default, если ключ отсутствует
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

                # Инициализация web3-адаптеров, если в режиме web3
        if self.market_mode == "web3":
            for sym in self.symbols_list:
                adapter = self.market_adapter.get_adapter(sym)
                if adapter and hasattr(adapter, 'initialize'):
                    logger.info(f"Initializing web3 adapter for {sym} ...")
                    await adapter.initialize()
                if adapter:
                    self.nonce_manager = adapter.nonce_manager
                    self.mutation_engine.nonce_manager = self.nonce_manager

                    # Обновляем executor для web3-режима актуальным адаптером
        if self.market_mode == "web3":
            adapter = self.market_adapter.get_adapter(self.symbols_list[0]) if self.symbols_list else None
            self.executor = build_backend(self.node_id, adapter, self.is_leader)

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
        logger.info("Node stopped.")
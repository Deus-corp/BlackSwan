import os, time, random, uuid, hashlib, asyncio, logging, sys, signal
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

import logging
logger = logging.getLogger("SwarmNode")
trade_logger = logging.getLogger("SwarmNode.Trade")
# Уровень устанавливается из переменной окружения LOG_LEVEL (по умолчанию INFO)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

EXPECTED_RETURN_RATE = 0.1 * 0.05
MAX_NORMALIZED_CAPITAL = 10000.0

# LLM mutation counters (глобально, т.к. в каждом процессе они независимы)
_llm_mutation_count = 0
_llm_mutation_total_impact = 0.0
_last_capital = None          # запоминаем предыдущий капитал для расчёта impact

def note_llm_mutation():
    global _llm_mutation_count
    _llm_mutation_count += 1

def update_llm_impact(current_capital: float):
    global _llm_mutation_total_impact, _last_capital
    if _last_capital is not None:
        impact = current_capital - _last_capital
        _llm_mutation_total_impact += impact
    _last_capital = current_capital

def get_llm_stats() -> Tuple[int, float]:
    avg = _llm_mutation_total_impact / _llm_mutation_count if _llm_mutation_count else 0.0
    return _llm_mutation_count, avg

class SwarmNode:
    def __init__(self) -> None:
        # конфигурация
        self.node_id: str = os.environ.get("NODE_ID", str(uuid.uuid4()))
        self.port: int = int(os.environ.get("PORT", 8000))
        self.peers: List[str] = [p for p in os.environ.get("PEERS", "").split(",") if p]

        self.market_url: Optional[str] = os.environ.get("MARKET_URL")
        self.market_mode: str = os.environ.get("MARKET_MODE", "sim")
        self.live_market: Optional[BinanceTestnetAdapter] = None
        if self.market_mode == "live":
            self.live_market = BinanceTestnetAdapter(symbol=os.environ.get("TRADING_SYMBOL", "BTC/USDT"))

        self.burn_rate: float = float(os.environ.get("BURN_RATE", 0.5))
        self.failure_prob: float = float(os.environ.get("FAILURE_PROB", 0.0))
        self.gossip_interval: float = 1.5
        self.max_state: int = 200
        self.ttl: int = 300
        self.max_import: int = 2
        self.import_cooldown: int = 5

        # компоненты
        self.crypto: CryptoManager = CryptoManager()
        self.key_manager = KeyManager()
        self.reputation: ReputationManager = ReputationManager()
        self.reputation_blacklist_threshold: float = 0.3

        # === ПАМЯТЬ ДОЛЖНА БЫТЬ ГОТОВА ДО CRDTАдаптера ===
        self.memory_api_enabled: bool = os.environ.get("MEMORY_API_ENABLED", "false").lower() == "true"
        self.memory_api: LocalMemoryAPI = LocalMemoryAPI(
            node_id=self.node_id,
            storage=None  # storage будет назначен позже, после создания CRDT
        )

        # Создаём CRDTAdapter (передаём memory_api, если нужно)
        self.crdt: CRDTAdapter = CRDTAdapter(
            node_id=self.node_id,
            memory_api=self.memory_api if self.memory_api_enabled else None,
            reputation=self.reputation
        )

        # Теперь у нас есть storage из CRDTAdapter — подключаем его к памяти
        if self.memory_api_enabled:
            self.memory_api.storage = self.crdt.storage


        self.gossip: SafeGossipAdapter = SafeGossipAdapter(self.crdt)
        self.gossip.set_reputation_manager(self.reputation)

        # Ключи для подписи геномов (если GOSSIP_SIGNING_ENABLED=true)
        self.gossip_private_key = self.key_manager.get_gossip_private_key()
        self.gossip_public_key = self.gossip_private_key.public_key()
        self.gossip_public_bytes = public_key_bytes(self.gossip_public_key)
        self.gossip_key_id = sha256(self.gossip_public_bytes)
        self.gossip_seq_no = 0
        self.gossip_lamport_ts = 0

        self.engine: GeneticEngine = GeneticEngine(pop_size=10)
        self.engine.initialize()

        self.state: GlobalState = GlobalState()
        # Event store
        self.event_store = EventStore(
            ledger_path=os.environ.get("EVENT_LEDGER_PATH", "./data/ledgers/events.jsonl"),
            sqlite_path=os.environ.get("EVENT_SQLITE_PATH", "./data/ledgers/events.db"),
        )
        self._trace_id: Optional[str] = None

        best = self.state.get_best_genomes(top_n=1)
        self.current_params: Dict[str, float] = list(best.values())[-1] if best else {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
        self.dispatcher: ROIDispatcher = ROIDispatcher(config=self.current_params)

        self.survival: SurvivalEvaluator = SurvivalEvaluator()
        self.survival.dq = 0.02
        self.survival.liveness = 1.0

        self.curiosity: CuriosityEngine = CuriosityEngine(window_size=10, surprise_threshold=0.3)
        self.meta_agent: MetaPOMDPAgent = MetaPOMDPAgent()
        self.llm = LLMClient()

                # storage уже создан для CRDT, передадим его в память
        self.memory_api: LocalMemoryAPI = LocalMemoryAPI(
            node_id=self.node_id,
            storage=self.crdt.storage  # передаём тот же CRDTStorage
        )

        self.memory: EpisodicMemory = EpisodicMemory(max_size=500)
        self.semantic: SemanticMemory = SemanticMemory()
        self.memory_api: LocalMemoryAPI = LocalMemoryAPI(node_id=self.node_id)
        self.memory_api_enabled: bool = os.environ.get("MEMORY_API_ENABLED", "false").lower() == "true"

        # runtime‑состояние
        self.capital: float = 1000.0
        self.step_count: int = 0
        self.last_import_step: int = 0
        self._prev_price: float = 100.0
        self._prev_prev_price: float = 100.0

        self._seed_from_memory()

    #------------------------------------------------------------
    def _llm_mutate(self, params: Dict[str, float], context: str) -> Dict[str, float]:
        """Мутация параметров через LLM."""
        prompt = f"""You are a trading strategy optimizer for the Kelly criterion.

Current market context:
{context}

Current strategy parameters:
{params}

Suggest a small adjustment to these parameters that could improve the strategy.
Respond ONLY with the adjusted parameters in JSON format, like:
{{"max_risk_per_trade": X, "phi_llm": Y}}"""
        
        try:
            response = self.llm.generate(prompt, max_tokens=64)
            # Парсим JSON из ответа
            import json
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                new_params = json.loads(response[start:end])
                for k in new_params:
                    new_params[k] = max(0.0001, min(1.0, float(new_params[k])))
                return new_params
        except Exception:
            pass
        return params  # fallback: возвращаем исходные параметры

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
        sig = genome.get("signature")
        pubkey = genome.get("origin_pubkey")
        if sig and pubkey:
            payload = {"params": genome.get("params", {}), "fitness": genome.get("fitness", 0.0)}
            if not CryptoManager.verify(payload, sig, pubkey):
                return False
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
    async def get_market_tick(self, session: aiohttp.ClientSession) -> dict:
        if self.market_mode == "live" and self.live_market:
            tick = await self.live_market.get_ticker()
            if tick is not None:
                # Масштабируем цену
                scale = float(os.environ.get("PRICE_SCALE", 10000))
                tick['price'] = tick.get('price', tick.get('ask', 50000))  # fallback
                tick['price'] = tick['price'] / scale
                return tick
            # Иначе рынок закрыт – fallback к симуляции
        # Старое поведение (симуляция)
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

                market = await self.get_market_tick(session)
                self.capital -= self.burn_rate
                if self.capital <= 0:
                    logger.info(f"[{self.node_id}] died")
                    return

                expected = market["price"] * EXPECTED_RETURN_RATE
                _, approved = self.survival.evaluate_trade(self.capital, expected)
                if approved:
                    fraction, _ = self.dispatcher.evaluate(market, self.capital)
                    if fraction > 0:
                        ret = market["price"] * fraction * 0.1
                        prev_capital = self.capital
                        self.capital *= (1 + ret)
                        self.capital -= 1.0
                        self.survival.dq = min(1.0, self.survival.dq + 0.001)
                        # Логирование сделки
                        logger.debug(
                            f"[{self.node_id}] TRADE | step={self.step_count} "
                            f"price={market['price']:.2f} fraction={fraction:.4f} "
                            f"ret={ret:.6f} capital_before={prev_capital:.2f} "
                            f"capital_after={self.capital:.2f} dq={self.survival.dq:.3f} "
                            f"params={self.current_params}"
                        )

                        # Запись события сделки
                        self.event_store.append(Event.create(
                            node_id=self.node_id,
                            event_type="trade_executed",
                            payload={
                                "step": self.step_count,
                                "price": market["price"],
                                "fraction": fraction,
                                "ret": ret,
                                "capital_before": prev_capital,
                                "capital_after": self.capital,
                                "dq": self.survival.dq,
                                "params": self.current_params,
                                "trace_id": self._trace_id,
                            },
                            parent_id=self._trace_id,
                        ))

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

                        # --- отправка с подписью или без ---
                        if os.environ.get("GOSSIP_SIGNING_ENABLED", "false").lower() == "true":
                            # Собираем подписанный конверт
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
                            # Старое поведение
                            payload = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]}
                            genome_dict["signature"] = self.crypto.sign(payload)
                            genome_dict["origin_pubkey"] = self.crypto.public_bytes_hex
                            await self.crdt.add_genome(genome_dict)

                    # LLM-мутация чемпиона (каждые 200 шагов)
                    if self.step_count % 200 == 0:
                        context = f"volatility={self._current_volatility():.3f}, dq={self.survival.dq:.3f}, capital={self.capital:.2f}"
                        new_params = self._llm_mutate(self.engine.champion[0], context)
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

                    # Сохраняем сводку в новую память, если API включено
                    if self.memory_api_enabled:
                        record = MemoryRecord(
                            id="",  # будет сгенерирован автоматически
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

                    # Статистика новой памяти (если включено)
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

                # ---- добавляем сюда ----
                update_llm_impact(self.capital)

                await asyncio.sleep(0.5)

    @staticmethod
    def _recombine(g1: dict, g2: dict) -> dict:
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
            "lineage": (g1.get("lineage", [])[-5:] + [os.environ.get("NODE_ID", "unknown")]),
            "ts": time.time(),
        }

    async def start(self) -> None:
        logger.info(f"[{self.node_id}] port={self.port} peers={self.peers}")
        await asyncio.gather(
            self.gossip.start(),
            self.main_loop(),
        )

    async def start(self) -> None:
        logger.info(f"[{self.node_id}] port={self.port} peers={self.peers}")

        loop = asyncio.get_running_loop()
        shutdown_event = asyncio.Event()

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
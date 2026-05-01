import os
import time
import random
import uuid
import hashlib
import asyncio
import logging
from typing import Dict, Any, Optional, List

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

logger = logging.getLogger("SwarmNode")

# ================= CONFIG =================

EXPECTED_RETURN_RATE = 0.1 * 0.05
MAX_NORMALIZED_CAPITAL = 10000.0


class SwarmNode:
    def __init__(self):
        self.node_id = os.environ.get("NODE_ID", str(uuid.uuid4()))
        self.port = int(os.environ.get("PORT", 8000))
        self.peers = [p for p in os.environ.get("PEERS", "").split(",") if p]
        self.market_url = os.environ.get("MARKET_URL")
        self.burn_rate = float(os.environ.get("BURN_RATE", 0.5))
        self.failure_prob = float(os.environ.get("FAILURE_PROB", 0.0))
        self.gossip_interval = 1.5
        self.max_state = 200
        self.ttl = 300
        self.max_import = 2
        self.import_cooldown = 5

        # Компоненты
        self.crypto = CryptoManager()
        self.reputation = ReputationManager()
        self.reputation_blacklist_threshold = 0.3
        self.crdt = CRDTAdapter(self.node_id)
        self.gossip = SafeGossipAdapter(self.crdt)
        self.gossip.set_reputation_manager(self.reputation)

        self.engine = GeneticEngine(pop_size=10)
        self.engine.initialize()
        self._seed_from_memory()

        self.state = GlobalState()
        best = self.state.get_best_genomes(top_n=1)
        self.current_params = list(best.values())[-1] if best else {"max_risk_per_trade": 0.05, "phi_llm": 0.15}
        self.dispatcher = ROIDispatcher(config=self.current_params)

        self.survival = SurvivalEvaluator()
        self.survival.dq = 0.02
        self.survival.liveness = 1.0

        self.curiosity = CuriosityEngine(window_size=10, surprise_threshold=0.3)
        self.meta_agent = MetaPOMDPAgent()
        self.memory = EpisodicMemory(max_size=500)

        self.capital = 1000.0
        self.step_count = 0
        self.last_import_step = 0

    def _seed_from_memory(self):
        """Добавляет в популяцию параметры из похожих рыночных ситуаций."""
        if len(self.memory) == 0:
            return
        # Вычисляем текущую волатильность (очень грубо, по последней цене)
        current_volatility = 0.02  # значение по умолчанию, можно улучшить
        current_dq = self.survival.dq
        similar = self.memory.find_similar(current_volatility, current_dq, top_k=3)
        for rec in similar:
            try:
                genome = self.dict_to_genome({"params": rec["params"]})
                self.engine.add_genome(genome)
            except:
                pass

    # ---- helpers ----
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
        return True
                # Фильтр по репутации
        pubkey = genome.get("origin_pubkey")
        if pubkey and not self.reputation.is_trusted(pubkey):
            return False

    def make_genome(self, params, fitness):
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
        return base * bias

    def population_diversity(self):
        pop = self.engine.population
        if not pop:
            return 0
        sigs = {hashlib.md5(str(sorted(g.params.items())).encode()).hexdigest() for g in pop if isinstance(g, Genome)}
        return len(sigs) / len(pop) if pop else 0

    def population_niche_counts(self):
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

    # ---- market ----
    async def get_market_tick(self, session):
        if self.market_url:
            try:
                async with session.get(self.market_url, timeout=1) as resp:
                    return await resp.json()
            except:
                pass
        return {"price": random.uniform(90, 110)}

    # ---- main loop ----
    async def main_loop(self):
        async with aiohttp.ClientSession() as session:
            while True:
                self.step_count += 1
                if self.failure_prob > 0 and random.random() < self.failure_prob:
                    logger.info(f"[{self.node_id}] failed")
                    return

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
                        self.capital *= (1 + ret)
                        self.capital -= 1.0
                        self.survival.dq = min(1.0, self.survival.dq + 0.001)

                # import genomes
                if self.step_count - self.last_import_step > self.import_cooldown:
                    remote = await self.crdt.get_top(10)
                    remote_genomes = []
                    for g in remote:
                        if self.accept_genome(g):
                            try:
                                remote_genomes.append(self.dict_to_genome(g))
                            except:
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
                    self.last_import_step = self.step_count

                # evolution
                if self.step_count % 50 == 0:
                    self.engine.evolve_generation()
                    if self.engine.champion[1] > 0:
                        genome_dict = self.make_genome(self.engine.champion[0], self.engine.champion[1])
                        payload = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]}
                        genome_dict["signature"] = self.crypto.sign(payload)
                        genome_dict["origin_pubkey"] = self.crypto.public_bytes_hex
                        await self.crdt.add_genome(genome_dict)

                    if self.engine.champion[1] > self.engine._fitness(self.current_params):
                        self.current_params = self.engine.champion[0]
                        self.dispatcher = ROIDispatcher(config=self.current_params)

                                    # Сохраняем в эпизодическую память
                    if self.engine.champion[1] > 0:
                        self.memory.add(
                            market_volatility=abs(market.get("price", 0.0) - getattr(self, '_prev_price', market.get("price", 0.0))) / max(1.0, market.get("price", 1.0)),
                            dq=self.survival.dq,
                            capital=self.capital,
                            params=self.engine.champion[0],
                            fitness=self.engine.champion[1],
                        )
                        self._prev_price = market.get("price", 0.0)

                    cur_niche = self.node_niche()
                    counts = self.population_niche_counts()
                    dom_niche = max(counts, key=counts.get)
                    logger.info(
                        f"[{self.node_id}] step={self.step_count} capital={self.capital:.2f} "
                        f"dq={self.survival.dq:.3f} fitness={self.engine.champion[1]:.4f} "
                        f"diversity={self.engine.diversity():.2f} crdt_size={len(self.crdt.state)} "
                        f"niche={cur_niche} dominant={dom_niche}"
                    )

                # curiosity + meta
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

                # prune + spot-check
                if self.step_count % 200 == 0:
                    await self.crdt.prune()
                    top = await self.crdt.get_top(20)
                    if top:
                        sample = random.choice(top)
                        pubkey = sample.get("origin_pubkey")
                        if pubkey and pubkey != self.crypto.public_bytes_hex:
                            actual_fit = self.engine._fitness(sample["params"])
                            claimed_fit = sample.get("fitness", 0.0)
                            self.reputation.update(pubkey, claimed_fit, actual_fit)

                await asyncio.sleep(0.5)

    @staticmethod
    def _recombine(g1, g2):
        child = {}
        for k in g1["params"]:
            val = g1["params"][k] if random.random() < 0.5 else g2["params"][k]
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

    async def start(self):
        logger.info(f"[{self.node_id}] port={self.port} peers={self.peers}")
        await asyncio.gather(
            self.gossip.start(),
            self.main_loop(),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    node = SwarmNode()
    try:
        asyncio.run(node.start())
    except KeyboardInterrupt:
        logger.info("Node stopped.")
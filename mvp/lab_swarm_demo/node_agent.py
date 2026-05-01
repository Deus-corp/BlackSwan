import os
import time
import random
import uuid
import hashlib
import asyncio
from typing import Dict, Any, Optional

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

# ================= CONFIG =================

NODE_ID = os.environ.get("NODE_ID", str(uuid.uuid4()))
PORT = int(os.environ.get("PORT", 8000))
PEERS = [p for p in os.environ.get("PEERS", "").split(",") if p]
MARKET_URL = os.environ.get("MARKET_URL", None)

BURN_RATE = float(os.environ.get("BURN_RATE", 0.5))
FAILURE_PROB = float(os.environ.get("FAILURE_PROB", 0.0))

GOSSIP_INTERVAL = 1.5
MAX_STATE = 200
TTL = 300  # seconds

MAX_IMPORT = 2
IMPORT_COOLDOWN = 5
ELITE_SIZE = 2

EXPECTED_RETURN_RATE = 0.1 * 0.05
MAX_NORMALIZED_CAPITAL = 10000.0

crypto = CryptoManager()
reputation = ReputationManager()

# ================= CRDT + GOSSIP (новые адаптеры) =================

crdt = CRDTAdapter(NODE_ID)
gossip = SafeGossipAdapter(crdt)

# ================= STABILISERS =================

def accept_genome(genome):
    if genome.get("fitness", 0) < 0.001:
        return False
    for v in genome.get("params", {}).values():
        if not (0 < v < 10):
            return False
    # Проверка подписи
    payload = {"params": genome.get("params", {}), "fitness": genome.get("fitness", 0.0)}
    if not CryptoManager.verify(payload, genome.get("signature", ""), genome.get("origin_pubkey", "")):
        return False
    return True

def make_genome(params, fitness):
    return {
        "params": params,
        "fitness": fitness,
        "niche": node_niche(),
        "origin": NODE_ID,
        "lineage": [NODE_ID],
        "ts": time.time(),
    }

def recombine(g1, g2):
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
        "lineage": (g1.get("lineage", [])[-5:] + [NODE_ID]),
        "ts": time.time(),
    }

def dict_to_genome(d: Dict[str, Any], niche: str = "exploration") -> Genome:
    """Преобразует словарь (из CRDT) в объект Genome."""
    return Genome(
        params={str(k): float(v) for k, v in d.get("params", d).items() if isinstance(v, (int, float))},
        fitness=float(d.get("fitness", 0.0)),
        niche=str(d.get("niche", niche)),
        lineage=list(d.get("lineage", [])[:12]),
    )

def local_score(genome: Genome) -> float:
    base = genome.fitness
    bias = 1.0
    if genome.niche == "survival":
        bias += min(0.5, survival.liveness)
    elif genome.niche == "exploration":
        bias += min(0.3, curiosity.surprise_threshold)
    elif genome.niche == "capital":
        bias += min(0.5, capital / 2000)
    return base * bias

def population_diversity(pop):
    if not pop:
        return 0
    sigs = {hashlib.md5(str(sorted(g.params.items())).encode()).hexdigest() for g in pop if isinstance(g, Genome)}
    return len(sigs) / len(pop) if pop else 0

def population_niche_counts(pop):
    counts = {"survival": 0, "capital": 0, "exploration": 0}
    for g in pop:
        if isinstance(g, Genome):
            niche = g.niche
        elif isinstance(g, dict):
            niche = g.get("niche", "exploration")
        else:
            continue
        counts[niche] = counts.get(niche, 0) + 1
    return counts

# ================= MARKET =================

async def get_market_tick(session):
    if MARKET_URL:
        try:
            async with session.get(MARKET_URL, timeout=1) as resp:
                return await resp.json()
        except:
            pass
    return {"price": random.uniform(90, 110)}

# ================= AGENT =================

engine = GeneticEngine(pop_size=10)
engine.initialize()

state = GlobalState()
best = state.get_best_genomes(top_n=1)
current_params = list(best.values())[-1] if best else {"max_risk_per_trade": 0.05, "phi_llm": 0.15}

dispatcher = ROIDispatcher(config=current_params)
survival = SurvivalEvaluator()
survival.dq = 0.02
survival.liveness = 1.0

curiosity = CuriosityEngine(window_size=10, surprise_threshold=0.3)
meta_agent = MetaPOMDPAgent()

capital = 1000.0
step_count = 0
last_import_step = 0

def node_niche():
    if survival.dq >= 0.8 or survival.liveness < 0.5:
        return "survival"
    elif capital > 50000 and survival.dq < 0.3:
        return "capital"
    else:
        return "exploration"

# ================= MAIN LOOP =================

async def main_loop():
    global capital, step_count, current_params, dispatcher, last_import_step

    async with aiohttp.ClientSession() as session:
        while True:
            step_count += 1

            if FAILURE_PROB > 0 and random.random() < FAILURE_PROB:
                print(f"[{NODE_ID}] failed")
                return

            market = await get_market_tick(session)

            capital -= BURN_RATE
            if capital <= 0:
                print(f"[{NODE_ID}] died")
                return

            expected = market["price"] * EXPECTED_RETURN_RATE
            _, approved = survival.evaluate_trade(capital, expected)

            if approved:
                fraction, _ = dispatcher.evaluate(market, capital)
                if fraction > 0:
                    ret = market["price"] * fraction * 0.1
                    capital *= (1 + ret)
                    capital -= 1.0
                    survival.dq = min(1.0, survival.dq + 0.001)

            # Import genomes from swarm with rate limiting + diversity-aware
            if step_count - last_import_step > IMPORT_COOLDOWN:
                remote = await crdt.get_top(10)
                remote_genomes = []
                for g in remote:
                    if accept_genome(g):
                        try:
                            remote_genomes.append(dict_to_genome(g))
                        except:
                            pass

                scored = sorted(remote_genomes, key=local_score, reverse=True)
                preferred_niche = node_niche()
                counts = population_niche_counts(engine.population)
                total = sum(counts.values()) or 1
                selected = []

                for g in scored:
                    niche = g.niche
                    niche_share = counts.get(niche, 0) / total
                    accept_prob = 0.2
                    if niche == preferred_niche:
                        accept_prob = 1.0
                    elif niche_share > 0.5:
                        accept_prob = 0.3
                    if random.random() < accept_prob:
                        selected.append(g)
                    if len(selected) >= MAX_IMPORT:
                        break

                for g in selected:
                    if engine.population:
                        parent_obj = random.choice(engine.population)
                        if isinstance(parent_obj, Genome):
                            parent_dict = {
                                "params": parent_obj.params,
                                "fitness": parent_obj.fitness,
                                "niche": parent_obj.niche,
                                "lineage": parent_obj.lineage,
                            }
                        else:
                            parent_dict = parent_obj  # уже словарь
                    else:
                        continue

                    child_dict = recombine(
                        parent_dict,
                        {"params": g.params, "fitness": g.fitness, "niche": g.niche, "lineage": g.lineage},
                    )
                    child_genome = dict_to_genome(child_dict, niche=g.niche)
                    engine.add_genome(child_genome)

                last_import_step = step_count

            # Evolution every 50 steps
            if step_count % 50 == 0:
                engine.evolve_generation()

                if engine.champion[1] > 0:
                    genome_dict = make_genome(engine.champion[0], engine.champion[1])
                    # подписываем параметры + фитнес
                    payload = {"params": genome_dict["params"], "fitness": genome_dict["fitness"]}
                    signature = crypto.sign(payload)
                    genome_dict["signature"] = signature
                    genome_dict["origin_pubkey"] = crypto.public_bytes_hex
                    await crdt.add_genome(genome_dict)

                if engine.champion[1] > engine._fitness(current_params):
                    current_params = engine.champion[0]
                    dispatcher = ROIDispatcher(config=current_params)

                current_niche = node_niche()
                counts = population_niche_counts(engine.population)
                dominant_niche = max(counts, key=counts.get)
                print(f"[{NODE_ID}] step={step_count} capital={capital:.2f} "
                      f"dq={survival.dq:.3f} fitness={engine.champion[1]:.4f} "
                      f"diversity={engine.diversity():.2f} "
                      f"crdt_size={len(crdt.state)} niche={current_niche} dominant={dominant_niche}")

            # Curiosity + Meta every 100 steps
            if step_count % 100 == 0:
                hypothesis = curiosity.update(market)
                if hypothesis:
                    engine.add_genome(dict_to_genome(hypothesis))

                norm_cap = min(1.0, capital / MAX_NORMALIZED_CAPITAL)
                surprise = curiosity.prediction_errors[-1] if curiosity.prediction_errors else 0.0
                weights = meta_agent.update(
                    dq=survival.dq,
                    liveness=survival.liveness,
                    capital=norm_cap,
                    surprise=surprise
                )
                survival.config["lambda"] = weights["w_capital"]

                if meta_agent.current_scenario in ("crisis", "stealth_mode"):
                    engine.set_mutation_rate(0.1)
                elif meta_agent.current_scenario == "exploration":
                    engine.set_mutation_rate(0.5)
                else:
                    engine.set_mutation_rate(0.25)

            if step_count % 200 == 0:
                await crdt.prune()
                # Выбираем случайный геном из CRDT и перепроверяем его фитнес
                top = await crdt.get_top(20)
                if top:
                    sample = random.choice(top)
                    if sample.get("origin_pubkey") != crypto.public_bytes_hex:
                        # вычисляем реальный фитнес на наших данных
                        actual_fit = engine._fitness(sample["params"])
                        claimed_fit = sample.get("fitness", 0.0)
                        reputation.update(sample["origin_pubkey"], claimed_fit, actual_fit)

            await asyncio.sleep(0.5)

# ================= START =================

async def start():
    print(f"[{NODE_ID}] port={PORT} peers={PEERS}")
    await asyncio.gather(
        gossip.start(),
        main_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        print("Node stopped.")
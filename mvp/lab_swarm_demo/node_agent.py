import os
import time
import random
import uuid
import asyncio
import aiohttp
from aiohttp import web

from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from sim.genetic_engine import GeneticEngine
from sim.survival_evaluator import SurvivalEvaluator
from sim.curiosity_engine import CuriosityEngine
from sim.meta_pomdp_agent import MetaPOMDPAgent
from src.core.crdt_adapter import CRDTAdapter

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

# ================= CRDT (Delta + Versioned LWW) =================

class CRDTState:
    def __init__(self):
        self.state = {}
        self.version = 0
        self.lock = asyncio.Lock()

    async def add_genome(self, params, fitness):
        async with self.lock:
            gid = str(uuid.uuid4())
            self.version += 1
            self.state[gid] = {
                "params": params,
                "fitness": fitness,
                "ts": time.time(),
                "node": NODE_ID,
                "ver": self.version
            }

    async def merge(self, remote_items):
        async with self.lock:
            for gid, val in remote_items.items():
                if gid not in self.state:
                    self.state[gid] = val
                else:
                    local = self.state[gid]
                    if (val["ver"], val["node"]) > (local["ver"], local["node"]):
                        self.state[gid] = val

    async def get_delta(self, known_versions):
        async with self.lock:
            delta = {}
            for gid, val in self.state.items():
                if gid not in known_versions or known_versions[gid] < val["ver"]:
                    delta[gid] = val
            return delta

    async def get_versions(self):
        async with self.lock:
            return {gid: val["ver"] for gid, val in self.state.items()}

    async def get_top(self, n=5):
        async with self.lock:
            return sorted(self.state.values(), key=lambda x: x["fitness"], reverse=True)[:n]

    async def prune(self):
        async with self.lock:
            now = time.time()
            # TTL
            self.state = {
                k: v for k, v in self.state.items()
                if now - v["ts"] < TTL
            }
            # size cap
            if len(self.state) > MAX_STATE:
                top = sorted(self.state.items(), key=lambda x: x[1]["fitness"], reverse=True)[:MAX_STATE]
                self.state = dict(top)

crdt = CRDTAdapter(NODE_ID)

# ================= PEER REPUTATION =================

peer_score = {p: 1.0 for p in PEERS}

def update_peer(peer, success):
    if peer not in peer_score:
        peer_score[peer] = 1.0
    peer_score[peer] *= (1.05 if success else 0.7)
    peer_score[peer] = max(0.1, min(2.0, peer_score[peer]))

def pick_peer():
    if not PEERS:
        return None
    weights = [peer_score.get(p, 1.0) for p in PEERS]
    return random.choices(PEERS, weights=weights)[0]

# ================= STABILISERS =================

def accept_genome(genome):
    if genome.get("fitness", 0) < 0.001:
        return False
    for v in genome.get("params", {}).values():
        if not (0 < v < 10):
            return False
    return True

def make_genome(params, fitness):
    return {
        "params": params,
        "fitness": fitness,
        "niche": node_niche(),
        "origin": NODE_ID,
        "lineage": [NODE_ID],
        "ts": time.time()
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
        "ts": time.time()
    }

def local_score(genome):
    base = genome["fitness"]
    bias = 1.0
    if genome.get("niche") == "survival":
        bias += min(0.5, survival.liveness)
    elif genome.get("niche") == "exploration":
        bias += min(0.3, curiosity.surprise_threshold)
    elif genome.get("niche") == "capital":
        bias += min(0.5, capital / 2000)
    return base * bias

def population_diversity(pop):
    return len(set(str(p) for p in pop))

def population_niche_counts(pop):
    counts = {"survival": 0, "capital": 0, "exploration": 0}
    for g in pop:
        niche = g.get("niche", "exploration")
        counts[niche] = counts.get(niche, 0) + 1
    return counts

# ================= GOSSIP =================

async def gossip_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            peer = pick_peer()
            if not peer:
                await asyncio.sleep(GOSSIP_INTERVAL)
                continue
            try:
                known = await crdt.get_versions()
                async with session.post(f"{peer}/gossip", json={"versions": known}, timeout=1) as resp:
                    data = await resp.json()
                    delta = data.get("delta", {})
                    filtered_delta = {}
                    trust = peer_score.get(peer, 1.0)
                    for k, v in delta.items():
                        if not accept_genome(v):
                            continue
                        # Trust-weighted acceptance
                        if random.random() < min(1.0, trust):
                            filtered_delta[k] = v
                    await crdt.merge(filtered_delta)
                    update_peer(peer, True)
            except:
                update_peer(peer, False)
            await asyncio.sleep(GOSSIP_INTERVAL)

# ================= HTTP =================

routes = web.RouteTableDef()

@routes.post("/gossip")
async def gossip_handler(request):
    data = await request.json()
    remote_versions = data.get("versions", {})
    delta = await crdt.get_delta(remote_versions)
    await crdt.merge(data.get("delta", {}))
    return web.json_response({"delta": delta})

async def run_server():
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

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
    """Determine the node's preferred niche based on current state."""
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

            expected = market["price"] * 0.1 * 0.05
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
                filtered = [g for g in remote if accept_genome(g)]
                scored = sorted(filtered, key=local_score, reverse=True)
                preferred_niche = node_niche()
                counts = population_niche_counts(engine.population)
                total = sum(counts.values()) or 1
                selected = []
                for g in scored:
                    if g.get("niche") == preferred_niche or random.random() < 0.2:
                        # Reduce probability if niche already dominates (>50% of population)
                        if counts.get(g.get("niche"), 0) / total > 0.5:
                            if random.random() < 0.3:
                                selected.append(g)
                        else:
                            selected.append(g)
                        if len(selected) >= MAX_IMPORT:
                            break
                for g in selected:
                    parent = random.choice(engine.population)
                    child = recombine({"params": parent, "niche": "local", "lineage": []}, g)
                    engine.population.append(child["params"])
                    if len(engine.population) > engine.pop_size:
                        engine.population.pop(0)
                last_import_step = step_count

            # Evolution every 50 steps
            if step_count % 50 == 0:
                # Elitism: keep best before evolution
                elite = sorted(engine.population, key=lambda p: engine._fitness(p), reverse=True)[:ELITE_SIZE]
                engine.evolve_generation()
                # Restore elite
                engine.population[-ELITE_SIZE:] = elite

                if engine.champion[1] > 0:
                    genome = make_genome(engine.champion[0], engine.champion[1])
                    await crdt.add_genome(genome["params"], genome["fitness"])
                    print(f"[{NODE_ID}] share fitness={engine.champion[1]:.4f}")

                if engine.champion[1] > engine._fitness(current_params):
                    current_params = engine.champion[0]
                    dispatcher = ROIDispatcher(config=current_params)

                # Log metrics with niche information
                current_niche = node_niche()
                counts = population_niche_counts(engine.population)
                dominant_niche = max(counts, key=counts.get)
                print(f"[{NODE_ID}] step={step_count} capital={capital:.2f} dq={survival.dq:.3f} "
                      f"fitness={engine.champion[1]:.4f} diversity={population_diversity(engine.population)} "
                      f"crdt_size={len(crdt.state)} niche={current_niche} dominant={dominant_niche}")

            # Curiosity + Meta every 100 steps
            if step_count % 100 == 0:
                hypothesis = curiosity.update(market)
                if hypothesis:
                    engine.population.append(hypothesis)

                norm_cap = min(1.0, capital / 10000.0)
                surprise = curiosity.prediction_errors[-1] if curiosity.prediction_errors else 0.0
                weights = meta_agent.update(
                    dq=survival.dq,
                    liveness=survival.liveness,
                    capital=norm_cap,
                    surprise=surprise
                )
                survival.config["lambda"] = weights["w_capital"]

                # Adaptive mutation rate
                if meta_agent.current_scenario in ("crisis", "stealth_mode"):
                    engine.set_mutation_rate(0.1)
                elif meta_agent.current_scenario == "exploration":
                    engine.set_mutation_rate(0.5)
                else:
                    engine.set_mutation_rate(0.25)

            if step_count % 200 == 0:
                await crdt.prune()

            await asyncio.sleep(0.5)

# ================= START =================

async def start():
    print(f"[{NODE_ID}] port={PORT} peers={PEERS}")
    await asyncio.gather(
        run_server(),
        gossip_loop(),
        main_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        print("Node stopped.")
import os
import time
import random
import threading
import requests
import uuid
import json

from src.economy.roi_dispatcher import ROIDispatcher
from src.core.global_state import GlobalState
from sim.genetic_engine import GeneticEngine
from sim.survival_evaluator import SurvivalEvaluator
from sim.curiosity_engine import CuriosityEngine
from sim.meta_pomdp_agent import MetaPOMDPAgent

# ================= CONFIG =================

NODE_ID = os.environ.get("NODE_ID", str(uuid.uuid4()))
PORT = int(os.environ.get("PORT", 8000))
PEERS = os.environ.get("PEERS", "").split(",") if os.environ.get("PEERS") else []
MARKET_URL = os.environ.get("MARKET_URL", None)

BURN_RATE = float(os.environ.get("BURN_RATE", 0.5))
FAILURE_PROB = float(os.environ.get("FAILURE_PROB", 0.0))

# ================= CRDT =================

class CRDTState:
    def __init__(self):
        self.state = {}
        self.lock = threading.Lock()

    def add_genome(self, params, fitness):
        gid = str(uuid.uuid4())
        with self.lock:
            self.state[gid] = {
                "params": params,
                "fitness": fitness,
                "timestamp": time.time(),
                "node_id": NODE_ID
            }

    def merge(self, remote):
        with self.lock:
            for gid, val in remote.items():
                if gid not in self.state:
                    self.state[gid] = val
                else:
                    local = self.state[gid]
                    if (val["timestamp"], val["node_id"]) > (local["timestamp"], local["node_id"]):
                        self.state[gid] = val

    def get_top(self, n=5):
        with self.lock:
            return sorted(
                self.state.values(),
                key=lambda x: x["fitness"],
                reverse=True
            )[:n]

    def prune(self, max_size=100):
        with self.lock:
            if len(self.state) > max_size:
                top = self.get_top(max_size)
                self.state = {str(i): g for i, g in enumerate(top)}

crdt = CRDTState()

# ================= GOSSIP =================

def gossip_loop():
    while True:
        if not PEERS:
            time.sleep(2)
            continue

        peer = random.choice(PEERS)
        try:
            res = requests.post(f"{peer}/sync", json=crdt.state, timeout=1)
            remote = res.json()
            crdt.merge(remote)
        except:
            pass

        time.sleep(2)

# ================= HTTP SERVER =================

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/sync", methods=["POST"])
def sync():
    remote = request.json
    crdt.merge(remote)
    return jsonify(crdt.state)

def run_server():
    app.run(host="0.0.0.0", port=PORT)

# ================= MARKET =================

def get_market_tick():
    if MARKET_URL:
        try:
            return requests.get(MARKET_URL, timeout=1).json()
        except:
            pass
    # fallback (симуляция)
    return {"price": random.uniform(90, 110)}

# ================= AGENT INIT =================

engine = GeneticEngine(pop_size=10)
engine.initialize()

state = GlobalState()

best = state.get_best_genomes(top_n=1)
if best:
    current_params = list(best.values())[-1]
else:
    current_params = {"max_risk_per_trade": 0.05, "phi_llm": 0.15}

dispatcher = ROIDispatcher(config=current_params)
survival = SurvivalEvaluator()
survival.dq = 0.02
survival.liveness = 1.0

curiosity = CuriosityEngine(window_size=10, surprise_threshold=0.3)
meta_agent = MetaPOMDPAgent()

capital = 1000.0
step_count = 0
last_champion_fitness = 0.0

print(f"[{NODE_ID}] started on port {PORT}, peers={PEERS}")

# ================= MAIN LOOP =================

def main_loop():
    global capital, step_count, current_params, dispatcher, last_champion_fitness

    while True:
        step_count += 1

        if FAILURE_PROB > 0 and random.random() < FAILURE_PROB:
            print(f"[{NODE_ID}] failed!")
            break

        market_data = get_market_tick()

        # --- survival ---
        if survival.should_hide():
            capital = survival.hide(capital)

        if survival.should_expand() and capital >= survival.config["expand_cost"]:
            if survival.expand(capital):
                capital -= survival.config["expand_cost"]

        capital -= BURN_RATE
        if capital <= 0:
            print(f"[{NODE_ID}] died")
            break

        # --- trading ---
        expected_return = market_data["price"] * 0.1 * 0.05
        _, approved = survival.evaluate_trade(capital, expected_return)

        if approved:
            fraction, _ = dispatcher.evaluate(market_data, capital)
            if fraction > 0:
                ret = market_data["price"] * fraction * 0.1
                capital *= (1 + ret)
                capital -= 1.0
                survival.dq = min(1.0, survival.dq + 0.001)

        # --- import genomes from CRDT ---
        top = crdt.get_top(3)
        for g in top:
            engine.population.append(g["params"])
            if len(engine.population) > engine.pop_size:
                engine.population.pop(0)

        # --- evolution ---
        if step_count % 50 == 0:
            engine.evolve_generation()

            if engine.champion[1] > last_champion_fitness:
                last_champion_fitness = engine.champion[1]

            # publish to CRDT
            if engine.champion[1] > 0:
                crdt.add_genome(engine.champion[0], engine.champion[1])
                print(f"[{NODE_ID}] shared genome {engine.champion[1]:.4f}")

            # upgrade strategy
            if engine.champion[1] > engine._fitness(current_params):
                current_params = engine.champion[0]
                dispatcher = ROIDispatcher(config=current_params)

        # --- curiosity + meta ---
        if step_count % 100 == 0:
            hypothesis = curiosity.update(market_data)
            if hypothesis:
                engine.population.append(hypothesis)

            norm_capital = min(1.0, capital / 10000.0)
            surprise = curiosity.prediction_errors[-1] if curiosity.prediction_errors else 0.0

            weights = meta_agent.update(
                dq=survival.dq,
                liveness=survival.liveness,
                capital=norm_capital,
                surprise=surprise
            )

            survival.config["lambda"] = weights["w_capital"]

        # --- maintenance ---
        if step_count % 200 == 0:
            crdt.prune()

        time.sleep(0.5)

# ================= START =================

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=gossip_loop, daemon=True).start()
    main_loop()
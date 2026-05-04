# BlackSwan 🦢

**Autonomous, self‑improving AI swarm with distributed evolution, economic sovereignty, and formally verified core.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://deus-corp.github.io/BlackSwan/)

---

## 📌 Project Status: **TRL‑4** (laboratory‑validated components)

- ✅ Formal TLA+ specifications for 8 protocols (including Ouroboros, SurvivalObjective, GeneticEngine, CuriosityEngine, AdaptiveMotivation)
- ✅ Economic simulator with multi‑agent sweep and stability zone discovery
- ✅ Docker lab swarm (8 nodes, Redis pub/sub, auto‑recovery)
- ✅ **Ouroboros v0.3** — distributed strategy evolution with Champion/Challenger and L2 memory
- ✅ **SurvivalObjective** — intelligent rejection of dangerous trades
- ✅ **GeneticEngine** — full population‑based evolution with formal verification
- ✅ **Adaptive Intrinsic Motivation** — Meta‑POMDP agent switches between 5 scenarios based on market conditions
- ✅ **Curiosity Engine** — proactive exploration of market anomalies
- ✅ Prototypes of **CRDT state** and **D2BFT consensus**
- 🧪 **Decentralized Gossip** — async CRDT‑gossip genome exchange (feature branch)
- ✅ CI/CD: unit tests, formal verification (local + GitHub Actions)
- 📖 [Documentation site](https://deus-corp.github.io/BlackSwan/)
- 📖 [Full TRL‑4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
- 🗺 [Roadmap](ROADMAP.md)
- 🏭 **Industrial CRDT** – SQLite-backed, op-based CRDT with deterministic LWW merge.
- 🛡️ **Secure Gossip** – HMAC-signed envelopes, replay protection, peer scoring and backoff.
- 🧬 **Speciated Genetic Engine** – species-based evolution with adaptive mutation and fitness cache.
- 🧠 **LLM-Powered Mutations** – a local LLM (Qwen2.5-1.5B) generates new strategy parameters instead of random mutations.
- ✅ **Multinode DeepSeek Swarm** — 4–5 nodes on DeepSeek-R1-Distill-Qwen-1.5B, shared read‑only model volume, resource limits for low‑RAM PCs (v2.13)
- ✅ **Multi-model benchmark** – 10 local LLMs compared (135M–1.7B). Report: [docs/reports/benchmark_10_models_2026-05-03.md](docs/reports/benchmark_10_models_2026-05-03.md)
- ✅ Spore Protocol validated — sustained fault‑recovery on 4‑node swarm (SmolLM2‑1.7B, 1h+ run)
- ✅ Signed genome exchange (Ed25519) active – cryptographically verified gossip for genome distribution.
- ✅ **LocalMemoryAPI** – layered memory (episodic, semantic, policy) with snapshot/restore.
- ✅ **Quarantine Buffer** – signature, reputation, and confidence checks for incoming memory records.
- ✅ **Gossip Filter** – replay protection (nonce‑cache) and monotonic sequence numbers across all gossip messages.
- 🧪 **Binance Testnet Adapter** – live price feed via CCXT, paper trading on BTC/USDT (enable with `MARKET_MODE=live`).
- ✅ **Persistent Memory** – SQLite‑backed storage for LocalMemoryAPI, survives node restarts.
- ✅ **Live Market Enhancements** – bid/ask pricing, market hours filter, multi‑symbol support (ETH/USDT).
- ✅ **Telegram Bot** – remote monitoring via /status, /nodes, /memory commands.
- ✅ **Improved Dashboard** – 2×2 layout with capital, fitness, diversity/CRDT, and niche pie chart.
- ✅ Event sourcing with append-only ledger and trace IDs.
- ✅ Gold filter and dataset export pipeline for future LoRA training.
- ✅ Health endpoint (`/health`), graceful shutdown, model integrity check.
- 🔑 **Centralized Key Manager** – isolated, env‑based secret store; private keys never leaked to logs.
- 📜 **Intelligence Contract v1.0** – formal, documented interface between Infrastructure and Intelligence layers.
- 🧱 **Logical Layer Separation** – code structured into `Infrastructure` (gossip, market, events) and `Intelligence` (LLM, strategies), ready for future sidecar extraction.
- 📊 **Gold Filter & Dataset Export** – automated selection of successful trading episodes for future LoRA fine‑tuning.

---

## 🧬 Key Features

- **Self‑Sovereign Economy** – built‑in market and Kelly‑criterion capital dispatcher.
- **Ouroboros Self‑Improvement** – genetic search for optimal strategies, genome exchange in the swarm, Champion/Challenger.
- **Survival Objective** – each node evaluates detection risk and refuses dangerous actions.
- **Adaptive Intrinsic Motivation** – dynamic balancing of capital, stealth, and curiosity via Meta‑POMDP.
- **Curiosity Engine** – autonomous detection of market anomalies and generation of research hypotheses.
- **Swarm Resilience** – automatic failure detection and Spore Protocol (node rebirth).
- **Formally Verified Core** – critical invariants proven in TLA+.
- **Defense in Depth** – multi‑layer isolation, traffic obfuscation.

---

## 🚀 Quick Start (local demo)

## 🎮 Swarm Control Panel
```bash
python3 swarm_control.py
```

## 🛠️ Swarm Configuration Guide

The default docker‑compose setup uses a local LLM and a simulated market.  
You can customise the swarm through environment variables in `docker-compose.async.yml`.

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_MODEL` | Which local LLM to use (`smollm2`, `qwen`, `deepseek`, …) | `smollm2` |
| `GOSSIP_SIGNING_ENABLED` | Enable Ed25519 signatures for genome exchange | `false` |
| `FAILURE_PROB` | Probability of node failure per step (Spore test) | `0.0` |
| `TOTAL_NODES` | Number of peers expected in the swarm | `4` |
| `MARKET_MODE` | `sim` (simulated) or `live` (Binance Testnet) | `sim` |
| `TRADING_SYMBOL` | Trading pair for live market | `BTC/USDT` |
| `BINANCE_TESTNET_API_KEY` / `BINANCE_TESTNET_API_SECRET` | API credentials for live trading (store in `.env`) | – |

**Example – launch a 4‑node signed swarm with SmolLM2‑1.7B and Spore resilience:**

```bash
# In docker-compose.async.yml, set:
# LLM_MODEL=smollm17
# GOSSIP_SIGNING_ENABLED=true
# FAILURE_PROB=0.02
# TOTAL_NODES=4
docker compose -f mvp/lab_swarm_demo/docker-compose.async.yml up -d --scale node=4
```
**Example – live paper trading:**

```bash
# 1. Create .env file with your Binance Testnet keys
# 2. In docker-compose.async.yml, set:
# MARKET_MODE=live
# BINANCE_TESTNET_API_KEY=${BINANCE_TESTNET_API_KEY}
# BINANCE_TESTNET_API_SECRET=${BINANCE_TESTNET_API_SECRET}
docker compose -f mvp/lab_swarm_demo/docker-compose.async.yml up -d --scale node=4
```

## 🧪 Model Benchmark

```python
python model_benchmark.py   # automatically tests all local LLMs and saves logs to docs/logs/models/
```

## 🤖 Telegram Bot
```bash
export TELEGRAM_BOT_TOKEN=your_token  # или добавить в .env
python3 telegram_bot.py
```

## 📚 Documentation

- [Documentation site](https://deus-corp.github.io/BlackSwan/)
- [Architecture decisions](docs/architecture/)
- [Formal verification](formal/tla/)
- [Simulation report](docs/TRL4_simulation_baseline.md)
- [TRL‑4 Validation](docs/TRL4_VALIDATION_REPORT.md)
- [Ouroboros Report](docs/TRL4_OUROBOROS_REPORT.md)

---

## ❤️ Support the Project

BlackSwan is an independent research project. If you find it valuable,
consider supporting its development:

- **Crypto donations** — see [DONATIONS.md](DONATIONS.md)

All funds go toward infrastructure, compute resources, and further research.
Sponsorship does not confer any rights over the project.

---

## 📄 License

Dual‑licensed under MIT or Apache‑2.0, at your option.  
See [LICENSE-MIT](LICENSE-MIT.md) and [LICENSE-APACHE](LICENSE-APACHE.md).

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*
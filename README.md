# BlackSwan 🦢

**Autonomous, self‑improving AI swarm with distributed evolution, economic sovereignty, and formally verified core.**

[![Python Tests](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml/badge.svg)](https://github.com/Deus-corp/BlackSwan/actions/workflows/python-tests.yml)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://deus-corp.github.io/BlackSwan/)

---

## 🚀 Quick Start

### 1. 🎮 Console Control Panel

Interactive menu to start/stop/rebuild the swarm, change models, set API keys, and view logs – no Docker commands needed.

```bash
git clone https://github.com/Deus-corp/BlackSwan.git
cd BlackSwan
python3 swarm_control.py
```

### 2. 🌐 Web Control Panel

Open http://localhost:8080 in your browser to manage the swarm and see real‑time charts.

```bash
pip install fastapi uvicorn python-multipart
python3 web_control_panel.py
```

### 3. Download LLM Models

The swarm requires at least one local LLM model. Download the recommended ones:

```bash
# SmolLM2-1.7B (fast, low‑resource)
curl -L "https://huggingface.co/bartowski/SmolLM2-1.7B-Instruct-GGUF/resolve/main/SmolLM2-1.7B-Instruct-Q4_K_M.gguf" -o llama_cpp/SmolLM2-1.7B-Instruct-Q4_K_M.gguf

# DeepSeek-R1-Distill-Qwen-1.5B (best reasoning)
curl -L "https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf" -o llama_cpp/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf
```
Set LLM_MODEL=smollm17 or LLM_MODEL=deepseek in docker-compose.async.yml.

---

## 📌 Project Status: **TRL‑4** (laboratory‑validated components)

### Core & Formal Verification
- ✅ TLA+ specs for 8 protocols (Ouroboros, SurvivalObjective, GeneticEngine, CuriosityEngine, AdaptiveMotivation)
- ✅ Industrial CRDT – SQLite‑backed, op‑based with deterministic LWW merge
- ✅ Secure Gossip – HMAC‑signed envelopes, replay protection, peer scoring & backoff
- ✅ Gossip Filter – replay protection and monotonic sequence numbers across all messages
- ✅ Signed genome exchange (Ed25519) for cryptographically verified genome distribution

### Swarm & Communication
- ✅ Docker lab swarm (4–5 nodes) with auto‑recovery (Spore Protocol validated)
- ✅ Spore Protocol – sustained fault‑recovery on 4‑node swarm (SmolLM2‑1.7B, 1h+ run)
- ✅ Logical layer separation (Infrastructure / Intelligence layers) via documented Intelligence Contract v1.0

### Memory & Data Pipeline
- ✅ LocalMemoryAPI – layered memory (episodic, semantic, policy) with snapshot/restore & SQLite persistence
- ✅ Quarantine Buffer – signature, reputation, and confidence checks for incoming memory records
- ✅ Event sourcing – append‑only ledger with trace IDs
- ✅ Gold Filter & dataset export pipeline for future LoRA training

### LLM & Evolution
- ✅ Speciated Genetic Engine with adaptive mutation and fitness cache
- ✅ LLM‑Powered Mutations – local LLMs generate new strategy parameters
- ✅ Multi‑model benchmark – 10 local LLMs compared (135M–1.7B). Report: [benchmark](docs/reports/benchmark_10_models_2026-05-03.md)

### Security & Key Management
- 🔑 Centralized Key Manager – isolated, env‑based secret store; private keys never leaked to logs

### Observability & Operations
- ✅ Health endpoint (`/health`), graceful shutdown, model integrity check
- ✅ Improved Dashboard – 2×2 layout with capital, fitness, diversity/CRDT, and niche pie chart
- 🤖 Telegram Bot – remote monitoring via /status, /nodes, /memory

### Market & Trading
- 🧪 Binance Testnet Adapter – live price feed via CCXT, bid/ask pricing, market hours filter, multi‑symbol support
- 🧪 Web3 Testnet Adapter (stub) – prepared for Arbitrum Sepolia integration

- 🌐 **Multi‑Pair Trading** – single node trades BTC/USDT, ETH/USDT, SOL/USDT simultaneously.
- 🧠 **Internet Researcher** – gathers crypto news (sentiment) and on‑chain data for LLM context.
- 📈 **Binance Futures** – long/short trading with configurable leverage, stop‑loss, and dynamic leverage adjustment.
- 🛡️ **Spot/Futures Hedging** – automatic hedging of futures positions with spot orders (configurable ratio).
- 📊 **Order Book Analysis** – real‑time imbalance and delta volume for smarter entries.
- 📡 **TradingView Webhooks** – external trading signals injected directly into LLM context.
- 🌐 **Web3 Adapter** – Uniswap V3 price quotes and swap execution on Arbitrum Sepolia.
- 🖥️ **Web Control Panel** – full swarm management from browser (start/stop, config, logs, model switching).

### Documentation & Reports
- 📖 [Documentation site](https://deus-corp.github.io/BlackSwan/)
- 📖 [Full TRL‑4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
- 🗺 [Roadmap](ROADMAP.md)

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
- **Control Panel** – interactive CLI menu to start/stop/configure the swarm without Docker commands.

---

## 🛠️ Swarm Configuration Guide

The default docker‑compose setup uses a local LLM and a simulated market.  
You can customise the swarm through environment variables in `docker-compose.async.yml`.

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_MODEL` | Which local LLM to use (`smollm2`, `qwen`, `deepseek`, `smollm17`, `llama1b`, `abl_qwen05`, `unc_llama1b` …) | `smollm2` |
| `GOSSIP_SIGNING_ENABLED` | Enable Ed25519 signatures for genome exchange | `false` |
| `FAILURE_PROB` | Probability of node failure per step (Spore test) | `0.0` |
| `TOTAL_NODES` | Number of peers expected in the swarm | `4` |
| `BURN_RATE` | Capital burned per step (cost of living) | `0.1` |
| `MARKET_MODE` | `sim` (simulated), `live` (Binance Testnet), `futures` (Binance Testnet Futures), or `web3` (Arbitrum Sepolia) | `sim` |
| `TRADING_SYMBOLS` | Comma-separated list of trading pairs | `BTC/USDT,ETH/USDT,SOL/USDT` |
| `PRICE_SCALE` | Divider for live prices to fit strategy range | `10000` |
| `FUTURES_LEVERAGE` | Leverage for futures trading | `2` |
| `STOP_LOSS_PERCENT` | Maximum loss before stop-loss (percent) | `2.0` |
| `MAX_LEVERAGE` / `MIN_LEVERAGE` | Dynamic leverage range | `5` / `1` |
| `HEDGE_ENABLED` | Enable spot/futures hedging | `false` |
| `HEDGE_RATIO` | Portion of futures position to hedge with spot | `0.5` |
| `INTERNET_RESEARCHER_ENABLED` | Fetch crypto news and on-chain data | `false` |
| `ORDERBOOK_ANALYSIS_ENABLED` | Analyse order book imbalance | `false` |
| `TRADINGVIEW_WEBHOOK_ENABLED` / `TRADINGVIEW_WEBHOOK_PORT` | Enable TradingView signal webhook | `false` / `8888` |
| `WEB3_RPC_URL` | RPC endpoint for Web3 adapter | `https://sepolia-rollup.arbitrum.io/rpc` |
| `WEB3_PRIVATE_KEY` | Private key for Web3 transactions (store in `.env`) | – |
| `BINANCE_TESTNET_API_KEY` / `BINANCE_TESTNET_API_SECRET` | API credentials for live/futures trading (store in `.env`) | – |
| `ETHERSCAN_API_KEY` | API key for Internet Researcher (store in `.env`) | – |
| `MEMORY_API_ENABLED` | Enable layered persistent memory (`LocalMemoryAPI`) | `false` |
| `LOG_LEVEL` | Python logging level (`INFO`, `DEBUG`) | `INFO` |
| `EVENT_LEDGER_PATH` | Path to append-only event journal | `./data/ledgers/events.jsonl` |
| `EVENT_SQLITE_PATH` | Optional SQLite index for events | `./data/ledgers/events.db` |
| `TELEGRAM_BOT_TOKEN` | Token for Telegram monitoring bot (store in `.env`) | – |

## 🧪 Model Benchmark

```python
python tools/model_benchmark.py   # automatically tests all local LLMs and saves logs to docs/logs/models/
```

## 🤖 Telegram Bot

Commands: `/status`, `/nodes`, `/memory`, `/logs`, `/capital`, `/help`.
The bot answers with real-time swarm metrics and recent logs from running nodes.

```bash
export TELEGRAM_BOT_TOKEN=your_token  # or add to .env
python3 tools/telegram_bot.py
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

## ⚠️ Disclaimer

This software is experimental and has been tested exclusively on simulated and testnet environments (Binance Testnet, local sim). It is not financial advice. Use in real market conditions is at your own risk. Always verify strategies thoroughly and never trade with funds you cannot afford to lose.

---

## 📄 License

Dual‑licensed under MIT or Apache‑2.0, at your option.  
See [LICENSE-MIT](LICENSE-MIT.md) and [LICENSE-APACHE](LICENSE-APACHE.md).

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*
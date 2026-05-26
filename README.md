# BlackSwan 🦢

**A self-sovereign, evolutionary multi-agent trading swarm.**  
BlackSwan combines genetic algorithms, CRDT-based swarm memory, LLM-assisted strategy mutation, formal models, and guarded testnet execution.

> Current focus: stabilizing the modular swarm runtime, improving adapters, validating multi-agent behavior, and preparing a new dashboard.

[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue)](#license)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-brightgreen)](https://deus-corp.github.io/BlackSwan/)
[![First AI Swap](https://img.shields.io/badge/Sepolia%20swap-success-brightgreen)](https://sepolia.etherscan.io/tx/0xba457b54f9f674cd2118ba25a8caa342a3cf69c5685523eac814916739825213)

---

## ⚠️ Disclaimer

BlackSwan is experimental research software. It has been tested primarily in simulation, dry-run, and testnet environments. It is not financial advice. Do not use it with funds you cannot afford to lose.

The project includes safety gates such as dry-run mode, explicit execution approval, nonce management, and leader-election checks, but these mechanisms do not eliminate trading or software risk.

---

## 📌 Current Status — May 2026

**Readiness:** TRL-5 research prototype with modular swarm runtime, testnet execution support, CRDT coordination, and active hardening.

Recent validated state:

- ✅ 60+ unit tests passing.
- ✅ Swarm runtime smoke test passing.
- ✅ Trade heartbeat publishing fixed and visible to Overseer.
- ✅ Trade swarm can publish `trade_heartbeat` payloads into CRDT.
- ✅ Overseer can detect active trade nodes from CRDT state.
- ✅ Execution backend safety path restored for sim/web3/live/futures modes.
- ✅ Web3 execution backend refuses execution when leader checks fail.
- ✅ Legacy/prototype modules identified for quarantine.
- ✅ `src` pass completed, excluding `src/swarms`.
- ✅ `adapters` cleanup in progress.
- 🔜 Next: inspect `sim`, tune trade/security/explorer/improver swarms, then build the new dashboard.

---

## 🧬 What BlackSwan Does

BlackSwan is a distributed AI swarm where nodes can:

- observe market state,
- evolve trading parameters,
- exchange genomes through CRDT,
- publish heartbeats and events,
- apply meta-agent commands,
- execute simulated or testnet trades through guarded backends,
- recover from failures and continue operating.

The system is designed as a research platform for autonomous, self-improving agents with explicit safety boundaries.

---

## 🏗️ Architecture Overview

```text
BlackSwan
├── src/
│   ├── core/                 # CRDT, event store, gossip, global state
│   ├── swarms/               # Runtime swarms: trade, explorer, security, improver, overseer
│   ├── trading/              # Reusable trading domain: execution, market, capital, sync
│   ├── risk/                 # Circuit breakers, exposure, risk manager
│   ├── intelligence/         # LLM, memory, research, semantic/episodic modules
│   ├── memory/               # Local memory, quarantine, gold-filter export
│   ├── observability/        # Metrics, telemetry, Telegram notifier
│   ├── security/             # Crypto, keys, reputation, gossip envelopes
│   └── validation/           # Shared validators
├── adapters/                 # External integrations: Web3, Binance, futures, webhooks
├── sim/                      # Simulation/evolution components used by the trade swarm
├── tests/                    # Unit and runtime smoke tests
├── formal/                   # TLA+ specifications
└── docs/                     # Reports, architecture notes, validation docs
```

### Layering

* `src/swarms/*` is the runtime orchestration layer.
* `src/trading/*` is the reusable trading-domain library.
* `adapters/*` bridges external systems.
* `sim/*` currently contains both research scripts and runtime dependencies used by the trade swarm.
* `src/core/*` provides CRDT, event, gossip, and persistence infrastructure.

---

## 🚀 Quick Start: Local Runtime Smoke

From the repository root:

```bash
python -m pytest -q tests/unit/core tests/unit --maxfail=1
python -m src.testing.swarm_runtime_smoke
```

Expected result:

```text
60 passed
✅ swarm runtime smoke OK
```

---

## 🧪 Run Unit Tests

```bash
python -m pytest -q
```

Focused checks:

```bash
python -m pytest -q tests/unit/core/test_trade_execution_safety.py
python -m pytest -q tests/unit/economy/test_roi_dispatcher.py
```

---

## 🧠 Run the Modular Swarm Runtime

Example dry-run cluster:

```bash
python -m src.swarms.runtime.cluster_cli up \
  --trade-nodes 3 \
  --run-dir data/cluster_runtime/latest \
  --duration 300 \
  --safe \
  --echo
```

Inspect logs:

```bash
grep -R "Publishing trade heartbeat\|Published trade heartbeat\|trade_heartbeat\|Overseer snapshot" \
  data/cluster_runtime/latest/logs | tail -200
```

Expected heartbeat path:

```text
SwarmNode.Heartbeat - Publishing trade heartbeat payload: type=trade_heartbeat swarm=trade role=node
src.core.crdt_adapter - Custom data imported: ... (type=trade_heartbeat)
SwarmNode.Heartbeat - Published trade heartbeat.
Overseer snapshot: trade_nodes=...
```

---

## ⚙️ Execution Modes

BlackSwan supports multiple market/execution modes:

| Mode      | Description                                         |
| --------- | --------------------------------------------------- |
| `sim`     | Simulation/dry-run backend. Recommended default.    |
| `live`    | Binance spot/testnet adapter path.                  |
| `futures` | Binance futures/testnet adapter path.               |
| `web3`    | Ethereum Sepolia / Uniswap V3 testnet adapter path. |

Execution is guarded by:

* `dry_run`
* `execution_enabled`
* explicit approval commands
* deterministic leader election
* backend-level safety checks
* nonce manager coordination for Web3 transactions

---

## ⚡ Web3 Testnet Trading on Sepolia

1. Fund a Sepolia wallet with testnet ETH.
2. Configure environment variables:

```ini
MARKET_MODE=web3
TRADING_SYMBOLS=WETH/USDC
WEB3_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY
WEB3_PRIVATE_KEY=your_testnet_private_key

TEST_WEB3_SWAP_AMOUNT=0.001
TEST_WEB3_SWAP_SIDE=sell
WEB3_POOL_FEE=3000

EXECUTION_ENABLED=false
DRY_RUN=true
```

3. Start with dry-run first.
4. Enable real testnet execution only after validating logs and balances.

Important: never commit private keys.

---

## 🛡️ Safety Defaults

Recommended development defaults:

```ini
EXECUTION_ENABLED=false
DRY_RUN=true
MARKET_MODE=sim
```

For testnet execution, use explicit approvals and small amounts only.

The project currently includes:

* dry-run trade flow,
* execution backend guards,
* capital manager,
* exposure manager,
* circuit breaker,
* survival evaluator,
* nonce manager,
* leader-election gate,
* CRDT-visible heartbeats and commands.

---

## 🧩 Core Components

### CRDT and Events

* SQLite-backed CRDT layer.
* Operation-based records with deterministic merge behavior.
* CRDT adapter for genomes, heartbeats, commands, and swarm events.
* Event store for append-only event persistence.

Key files:

```text
src/core/crdt_layer.py
src/core/crdt_adapter.py
src/core/event_store.py
src/core/events.py
```

### Trade Swarm

The trade swarm is the most mature runtime swarm. It includes:

* market snapshots,
* trading flow,
* heartbeat publisher,
* meta-command application,
* maintenance service,
* risk checks,
* CRDT sync,
* evolution loop,
* execution backend integration.

Key files:

```text
src/swarms/trade/node.py
src/swarms/trade/heartbeat.py
src/swarms/trade/trading/flow.py
src/swarms/trade/meta/commands.py
src/swarms/trade/maintenance/service.py
```

### Adapters

External integration layer:

```text
adapters/base.py
adapters/live_market.py
adapters/futures_adapter.py
adapters/multi_pair_adapter.py
adapters/nonce_manager.py
adapters/orderbook_analyzer.py
adapters/tradingview_webhook.py
adapters/web3_testnet.py
```

Current adapter focus:

* consistent result contracts,
* safe close/cleanup,
* nonce safety,
* dry-run/live separation,
* async error handling,
* slippage protection,
* no private-key leakage.

### Simulation

`sim/` is currently both a research sandbox and a runtime dependency. The trade node imports:

```text
sim.curiosity_engine
sim.genetic_engine
sim.meta_pomdp_agent
sim.survival_evaluator
```

`src/trading/market_service.py` also uses:

```text
sim.engine.environment.MarketEnvironment
```

So `sim/` should not be deleted. It will be cleaned and split later into runtime modules and experiments.

---

## 📊 Observability

Current observability pieces:

* CRDT heartbeats.
* Overseer snapshots.
* Log inspection.
* Prometheus-compatible metrics.
* Telegram notifier.
* Event store.
* Runtime smoke checks.

Planned next dashboard work:

* `cluster_cli status --json`
* `cluster_cli doctor`
* CRDT reader for latest nodes/heartbeats
* log viewer
* node status cards
* capital/fitness/diversity charts
* command console with safety confirmation

---

## 🛠️ Configuration Guide

Common environment variables:

| Variable                      | Description                         | Default                  |
| ----------------------------- | ----------------------------------- | ------------------------ |
| `MARKET_MODE`                 | `sim`, `live`, `futures`, or `web3` | `sim`                    |
| `TRADING_SYMBOLS`             | Comma-separated trading pairs       | `WETH/USDC`              |
| `EXECUTION_ENABLED`           | Enables real execution path         | `false`                  |
| `DRY_RUN`                     | Forces dry-run behavior             | `true`                   |
| `WEB3_RPC_URL`                | Web3 RPC endpoint                   | —                        |
| `WEB3_PRIVATE_KEY`            | Testnet private key                 | —                        |
| `WEB3_POOL_FEE`               | Uniswap V3 pool fee                 | `3000`                   |
| `WEB3_SLIPPAGE_BPS`           | Web3 swap slippage in basis points  | `100`                    |
| `BINANCE_TESTNET_API_KEY`     | Binance testnet key                 | —                        |
| `BINANCE_TESTNET_API_SECRET`  | Binance testnet secret              | —                        |
| `FUTURES_LEVERAGE`            | Futures leverage                    | `2`                      |
| `STOP_LOSS_PERCENT`           | Futures stop-loss percent           | `2.0`                    |
| `HEDGE_ENABLED`               | Enables futures/spot hedging        | `false`                  |
| `ORDERBOOK_ANALYSIS_ENABLED`  | Enables order book analyzer         | `false`                  |
| `TRADINGVIEW_WEBHOOK_ENABLED` | Enables TradingView webhook         | `false`                  |
| `TRADINGVIEW_WEBHOOK_SECRET`  | Optional webhook shared secret      | —                        |
| `LOG_LEVEL`                   | Python logging level                | `INFO`                   |
| `EVENT_SQLITE_PATH`           | Event SQLite DB path                | `data/ledgers/events.db` |
| `TELEGRAM_BOT_TOKEN`          | Telegram bot token                  | —                        |

---

## 🧪 Formal Verification

Formal specifications live in:

```text
formal/tla/
```

Validated/prototyped areas include:

* Ouroboros/self-improvement,
* Survival Objective,
* Genetic Engine,
* Curiosity Engine,
* Adaptive Motivation,
* D2BFT prototype,
* swarm-level invariants.

---

## 📚 Documentation & Reports

* [Documentation site](https://deus-corp.github.io/BlackSwan/)
* [Architecture decisions](docs/architecture/)
* [Formal verification](formal/tla/)
* [TRL-4 Validation Report](docs/TRL4_VALIDATION_REPORT.md)
* [Ouroboros Report](docs/TRL4_OUROBOROS_REPORT.md)
* [Roadmap](ROADMAP.md)

---

## 🧭 Near-Term Plan

1. Finish inspecting and cleaning `adapters/`.
2. Inspect and split `sim/` into runtime-critical modules and experiments.
3. Tune trade swarm runtime.
4. Validate security/explorer/improver/overseer together.
5. Add `cluster_cli status --json` and `cluster_cli doctor`.
6. Build the new dashboard on top of runtime JSON status, CRDT, logs, and metrics.

---

## ❤️ Support the Project

BlackSwan is an independent research project. If you find it valuable, consider supporting its development:

* Crypto donations — see [DONATIONS.md](DONATIONS.md)

All funds go toward infrastructure, compute resources, and further research. Sponsorship does not confer any rights over the project.

---

## 📄 License

Dual-licensed under MIT or Apache-2.0, at your option.
See [LICENSE-MIT](LICENSE-MIT.md) and [LICENSE-APACHE](LICENSE-APACHE.md).

---

*BlackSwan © 2026. Experimental research software. Does not constitute financial advice or a call to action.*
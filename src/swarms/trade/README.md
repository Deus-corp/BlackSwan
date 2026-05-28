# Trade Swarm

Trade is one proving-ground swarm inside BlackSwan. It contains trade-specific
runtime orchestration, market data, execution, risk, capital, strategy, and
telemetry components.

The long-term goal is for trade to be self-contained under `src/swarms/trade/`,
while older `src/trading/*`, `adapters/*`, and `mvp/lab_swarm_demo/*` paths
remain compatibility wrappers during migration.

## Structure

```text
src/swarms/trade/
├── node.py              # Node entrypoint / runtime shell
├── meta_agent.py        # Meta-agent entrypoint / runtime shell
├── node_core/           # Future node internals
├── meta_agent_core/     # Future meta-agent internals
├── domain/              # Capital, models, leader selection, mutation metrics, sync
├── execution/           # Execution backend facades
├── market/              # Market data and selection facades
├── adapters/            # Exchange/webhook/external adapter facades
├── trading/             # Trade flow orchestration
├── maintenance/         # Maintenance services
├── context.py           # Runtime context/config
├── heartbeat.py         # Trade heartbeat publishing
└── risk.py              # Trade policy/risk primitives
```

## Migration rules

1. Keep `node.py` and `meta_agent.py` as stable entrypoints.
2. Move internals into `node_core/` and `meta_agent_core/` gradually.
3. Keep old imports working until all callers are migrated.
4. Prefer canonical imports from `src.swarms.trade.*` in new code.
5. Run unit tests and runtime smoke after each small move.

## Canonical import direction

New code should prefer:

```python
from src.swarms.trade.domain.capital import CapitalManager
from src.swarms.trade.execution import build_backend
from src.swarms.trade.market import MarketSnapshotService
```

Legacy paths under `src.trading.*`, `adapters.*`, and `mvp.lab_swarm_demo.*`
remain available for compatibility.
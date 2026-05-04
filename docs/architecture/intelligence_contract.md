# BlackSwan Node — Intelligence Contract v1.0

## Purpose
This document defines the interface between the **Infrastructure Layer** (Body) and the **Intelligence Layer** (Brain) of a swarm node. Currently, both layers run inside the same Python process, but the contract allows future separation into sidecar containers or dedicated services.

## Infrastructure Layer (Body)
Responsibilities:
- Peer-to-peer gossip (SafeGossipAdapter)
- Genome exchange & CRDT state (CRDTAdapter)
- Market data ingestion (BinanceTestnetAdapter / Web3Adapter)
- Replay protection & signature verification (GossipFilter)
- Local persistence of events & memory (EventStore, LocalMemoryAPI)
- Health reporting (/health endpoint)

**Inputs from Intelligence:**
- `genome_dict` to be published to swarm (via `CRDTAdapter.add_genome`)
- Trade execution requests (via `Web3Adapter.execute_swap`)

**Outputs to Intelligence:**
- Market tick: `async get_market_tick() -> dict` (price, bid, ask, symbol, timestamp)
- Remote genomes: `await crdt.get_top(n)` -> list of genome dicts
- Gossip events: internal dispatch to `handle_incoming(data)`

## Intelligence Layer (Brain)
Responsibilities:
- Strategy evaluation & genetic evolution (GeneticEngine)
- LLM-driven mutation (LLMClient)
- Survival assessment (SurvivalEvaluator)
- Curiosity engine & meta-POMDP (CuriosityEngine, MetaPOMDPAgent)
- Decision making (main_loop)

**Inputs from Infrastructure:**
- Market tick
- Remote genomes
- Current capital & risk state

**Outputs to Infrastructure:**
- New genome to publish
- Trade decision (future)

## Data Schemas (canonical)
### Market Tick
```json
{
  "price": 50000.00,
  "symbol": "BTCUSDT",
  "timestamp": 1714800000000,
  "bid": 49999.50,
  "ask": 50000.50
}
```
### Genome
```json
{
  "params": {"max_risk_per_trade": 0.05, "phi_llm": 0.15},
  "fitness": 0.95,
  "niche": "capital",
  "origin": "node-1",
  "lineage": ["node-1"],
  "ts": 1714800000.0
}
```

## Communication Protocols

Synchronous (current): Direct Python method calls within the same process.
Planned (future): gRPC or localhost HTTP API when separating into sidecar containers.

## Version History
v1.0 (2026-05-04): Initial contract based on current monolith architecture.
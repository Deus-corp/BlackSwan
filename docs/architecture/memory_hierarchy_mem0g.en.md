# Memory Hierarchy Mem0g

**Purpose:** Describe the architecture of the system's long-term memory — **Mem0g**. The module covers the four-level storage structure (L0–L3), knowledge consolidation mechanisms, quality control, conflict resolution strategies (CRDT), dynamic model routing, neuro-symbolic compression, and a preventive value drift detector. Memory is the foundation for learning, evolution, and swarm coordination.

---

## 1. Architecture Overview

Mem0g is an evolving, hierarchical, graph-vector memory for:
- Accumulating and structuring hybrid cycle experience.
- Preventing recurrence of errors (defect signatures).
- Consolidating raw logs (L1) into strategies (L2) for long-term use.
- Conflict-free knowledge replication between nodes (CRDT).
- Self-optimisation of its own architecture (L0 Meta-Mem0g).

### 1.1. Four-Level Hierarchy

| Level | Data Type | Storage | TTL / Update Frequency |
| :--- | :--- | :--- | :--- |
| **L0 (Meta)** | Records about memory configurations and their impact on metrics | Neo4j (HardState, BFT) + IPFS | Permanent, after each sleep-cycle |
| **L1 (Hot / Episodic)** | Raw iteration logs, reasoning chains | Qdrant (vector DB) | 24–48 h, cleared after consolidation |
| **L2 (Semantic / Distilled)** | Abstract strategies, patterns, error signatures | Neo4j (graph) + vector embeddings | Permanent, controlled by budget |
| **L3 (Procedural / Core)** | Critical invariants, Core DNA, terminal goals | Signed snapshots in IPFS/Arweave | Only through multi-model consensus |

---

## 2. Hybrid CRDT and Conflict Resolution

### 2.1. Hybrid Merge Strategy

Classic Last-Writer-Wins (LWW) loses data during concurrent updates. Mem0g uses a hybrid strategy:

| Field | Strategy | Rationale |
| :--- | :--- | :--- |
| `timestamp`, `vector_clock` | LWW | Metadata, latest source matters |
| `content` (text, code) | Semantic Merge (3-way) | Preserve all significant changes |
| `confidence`, `quality_score` | Average weighted by vector clocks | Objective aggregation |
| `graph_links` | Union with deduplication | Don't lose connections |

### 2.2. Strict AST-First Merge (for code artifacts)

Two-level merge for source code objects:
- **Level 1 — Strict AST Merge:** Deterministic AST merge without LLM. Result: `CleanMerged`, `Conflict`, or `SideEffectWarning`.
- **Level 2 — LLM Semantic Merge:** Only on `Conflict` at Level 1. `Architectus` generates property-based tests; `evolutiond` synthesises code passing all tests. On failure, a `Conflict Node` is created.

Expected effect: 70–85% reduction in Conflict Nodes.

---

## 3. Memory Consolidation (Sleep Cycle)

Launched every 12–24 hours or upon >500 raw L1 logs.

1. **Dual-Pass Distillation:** Extract facts (Pass 1) → synthesise strategy (Pass 2) → check for contradictions via Consistency Gate.
2. **JEPA Re-encoding:** New records encoded into latent space for fast search.
3. **L3 Invariant Check:** All new distilled principles verified against L3.0.
4. **L1 Cleanup:** Soft deletion of processed raw logs.

---

## 4. Predictive Consistency Router (PCR)

ML extension over `ConsistencyRouter` that predicts conflict probability for incoming SoftState updates and preemptively routes them to Semantic BFT, avoiding the creation of Conflict Nodes.

- **Model:** LightGBM / ONNX, trained on historical Conflict Nodes.
- **Effect:** 30–40% additional reduction in Conflict Nodes.

---

## 5. JEPA Layer (Joint-Embedding Predictive Architecture)

Translates knowledge storage into compact latent space without losing semantics of connections.

- **Encoder:** `Vagrant` (20% experts). Dimension: 1536 (float16).
- **Compression:** 15×+, semantic search latency <5 ms (p95), CRDT sync traffic reduced by 80%.

---

## 6. Dynamic Model Routing 2.0

Selects the optimal execution configuration for each task in real time across four axes: target node, species mask, expert percentage, quantisation. Optimised on a 3‑objective Pareto front (Quality, Latency, Cost/Energy).

---

## 7. Neuro-Symbolic L2 Compression (DSL Rules)

Transforms successful textual strategies (`DistilledWisdom`) into formal DSL rules executable by Rule VM without LLM. Match with LLM decision ≥ 95%.

---

## 8. Meta-Mem0g (L0) — Self-Optimising Meta-Memory

Autonomous collection, analysis, and optimisation of the Mem0g architecture itself. Optimisation categories: CRDT strategies, pruning formulas, distillation parameters, memory budgets.

---

## 9. Value Drift Early-Warning System

Preventive monitoring of slow semantic drift of L2/L3 principles. Drift Score computed as cosine distance between current embedding and baseline. Exceeding threshold triggers `value_drift_warning` and extraordinary Constitutional Debate.

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*
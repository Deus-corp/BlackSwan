# Genetic Evolution Engine

**Purpose:** Implement a continuous process of code self‑improvement through population‑based methods, LLM‑guided mutations, and a multi‑factor fitness function. The engine is the main supplier of candidates for the `Champion/Challenger` system and the key mechanism for achieving Open‑Endedness in system evolution.

---

## 1. Engine architecture

The engine is implemented as a service **`evolutiond`** (Rust) and operates on a population of variants for each critical module.

```
evolutiond/
├── population.rs # population management, selection, crossover
├── fitness.rs # fitness computation (refers to Validation Pipeline)
├── llm_mutator.rs # interaction with DeepSeek-V4 (Vagrant mask)
├── diversity.rs # Genetic Diversity Mandate
├── open_ended.rs # radical mutation detector
├── stepping_stones.rs # Stepping Stone Archive and PFV predictor
├── telemetry.rs # history storage in sled
└── hot_reload.rs # safe module replacement
```

---

## 2. LLM‑guided mutation

Unlike random mutations, `llm_mutator` receives the current code, telemetry (defect history, success rate) and generates a new version by purposefully changing the structure. Mutations use **DeepSeek‑V4 with the restricted expert mask `Vagrant` (20% experts)**. This reduces computational load and prevents overly "creative" changes that could destabilize the system.

```rust
// evolutiond/src/llm_mutator.rs
pub async fn mutate_with_context(&self, code: &str, telemetry: &Telemetry) -> String {
    let prompt = format!(...);
    // Call DeepSeek-V4 with X-Species-Mask: vagrant header
    self.deepseek_client.generate(&prompt, SpeciesMask::Vagrant).await
}
```
## 3. Fitness function
Fitness is computed as a weighted sum of metrics. The basic formula in Phase 2:

Fitness = 0.25 * valid_score + 0.25 * perf_score + 0.2 * novelty + 0.3 * frontier_score
• valid_score ∈ {0, 1} — whether deterministic validation was passed.
• perf_score = 1 — benchmark_regression (the lower the regression, the higher).
• novelty — cosine distance of code embeddings to the rest of the population.
• frontier_score — evaluation by Architectus (60% experts) or a local predictor.

The frontier_score weight may be replaced by resilience_score during active chaos testing. An adaptive fitness function with Bayesian weighting is described in Section 5 of the Cognitive_Evolution README.

## 4. Genetic Diversity Mandate
Purpose: Prevent population degeneration (mode collapse), when all individuals become variations of one successful genome.

Diversity Score is computed as the pairwise average cosine distance between embeddings of all individuals:

text
diversity = (2 / (N*(N-1))) * Σ_{i<j} (1 - cosine_similarity(emb_i, emb_j))
Thresholds:

• warning (< 0.15): ↑ mutation_rate by 50%, ↑ novelty weight in fitness, activate NES.
• critical (< 0.08): Re‑seed from archive (2–3 old genomes with high diversity), forced NES for 10 generations, elitism reset.

All diversity events are logged in L0 Meta-Mem0g.

## 5. Open‑Endedness Mandate
The system distinguishes two types of mutations:

• Incremental: improvement of existing code within the same paradigm.
• Radical: creation of a new abstraction that changes the way problems are solved (new DSL, consensus protocol, alternative memory architecture).

Radical mutations are detected by the creation of new syntactic constructs (macros, traits), an architectural shift, or the presence of a formal improvement proof (Z3). They receive a radical_bonus (up to +1.0 to fitness).

Periodically (every 30 days or upon diversity stagnation), Meta‑Innovation is launched — allocating 20% of Core Node resources to solve a "grand challenge" beyond current capabilities.

Details — in Open_Endedness.md.

## 6. Stepping Stone Archive and PFV
Genomes that do not pass the fitness threshold for immediate deployment but possess high novelty (novelty > 0.85) and structural complexity are stored in the Stepping Stone Archive (SSA). For them, Potential Future Value (PFV) is calculated — the predicted probability of becoming part of a future breakthrough.

• PFV model: lightweight neural network (Candle), trained on historical Innovation Archive data.
• Usage: 20% of new population individuals are initialized with random genomes from SSA; a special crossover operator with 10% probability selects the second parent from SSA.

Details — in Open_Endedness.md.

## 7. Integration with the sleep cycle
During sleep_cycle_consolidation (see Memory_Hierarchy_Mem0g), the genetic engine runs evolution for all active modules. The best genomes are saved in Mem0g L2 as "strategies" and can be used to initialize the population upon the next awakening or on other swarm nodes.

## 8. Configuration in evolutiond.toml

```toml
[population]
size = 10
elite_fraction = 0.25
crossover_rate = 0.7
mutation_rate = 0.3

[llm]
enabled = true
model = "deepseek-v4"
species_mask = "vagrant"
expert_percent = 20
context_size = 2048

[diversity]
enabled = true
warning_threshold = 0.15
critical_threshold = 0.08
check_interval_generations = 5
archive_size = 20

[open_endedness]
enabled = true
radical_bonus_max = 1.0

[stepping_stones]
enabled = true
novelty_threshold = 0.85
pfv_threshold = 0.3
archive_max_size = 500

[telemetry]
db_path = "/var/lib/swarm/evolution_db"
```
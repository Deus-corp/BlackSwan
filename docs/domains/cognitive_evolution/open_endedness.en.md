# Open‑Endedness Mandate

**Purpose:** Provide the system with the ability to evolve beyond the current search space — creating fundamentally new abstractions, protocols, and architectures, not just local improvements. This document describes the mechanisms for detecting, encouraging, and preserving radical mutations, as well as the infrastructure for accumulating “stepping stones” on the path to future breakthroughs.

---

## 1. The problem of evolutionary stagnation (Mode Collapse)

Despite measures to maintain diversity (novelty, Genetic Diversity Mandate), the genome population may over time converge to a local optimum — become extremely efficient at solving problems **that it itself generates**, but lose the ability to adapt to sudden environmental changes (“black swans”).

The Open‑Endedness Mandate prevents this by introducing special incentives for searching and preserving **radical innovations** — solutions that go beyond the existing paradigm.

---

## 2. Mutation classification

The system distinguishes two types of changes:

| Type | Description | Examples |
| :--- | :--- | :--- |
| **Incremental** | Improvement of existing code within the same paradigm | Loop optimization, replacing a sorting algorithm with a faster one |
| **Radical** | Creation of a new abstraction that changes the way problems are solved | Inventing a custom DSL for financial operations, a new consensus protocol, an alternative memory architecture |

---

## 3. Radical mutation detector

The `InnovationDetector` component analyzes each mutation by comparing it with the parent genome. A mutation is considered **radical** if **at least one** of the following holds:

1. **New syntactic constructs:** Creation of a new macro, trait, DSL‑like pattern (detected via AST differentiation).
2. **Architectural shift:** Transition from a monolithic structure to an actor model, introduction of a new interaction protocol, etc.
3. **Formal proof of improvement:** Presence of a Z3 predicate or TLA+ specification proving asymptotic improvement or a fundamental property of the new solution.

```rust
// evolutiond/src/open_ended.rs
impl InnovationDetector {
    pub fn classify_mutation(&self, genome: &Genome, base: &Genome) -> MutationType {
        let ast_diff = ast_merger::diff(&base.code, &genome.code);
        
        if ast_diff.has_new_macro() || ast_diff.has_new_trait() || ast_diff.has_dsl_pattern() {
            return MutationType::Radical;
        }
        if ast_diff.detects_architectural_shift() {
            return MutationType::Radical;
        }
        if let Some(proof) = genome.formal_proof {
            if verify_improvement_proof(&proof, base) {
                return MutationType::Radical;
            }
        }
        MutationType::Incremental
    }
}
```

## 4. Radical Bonus in the fitness function
Radical mutations receive an additional bonus to fitness:

text
Fitness = w1*valid_score + w2*perf_score + w3*novelty + w4*frontier_score + w5*radical_bonus
radical_bonus is calculated based on:

• Comparison with the Innovation Archive: if the genome is isomorphic to an already known abstraction, no bonus is awarded.
• Semantic distance to the nearest known paradigm.
• Presence of a formal proof: if valid, the bonus is multiplied by a factor up to 1.0.

Thus, the system receives a significant advantage (up to +1.0 to fitness) for creating a verified superior abstraction, even if its immediate performance is inferior to the current champion.

## 5. Innovation Archive

All radical mutations that successfully pass the full validation cycle and are deployed to production are stored in the Innovation Archive — a special collection in Mem0g L2.

An archive entry contains:

• The paradigm embedding (from Vagrant).
• The formal proof (Z3 predicate or TLA+ specification).
• Meta‑information: invention date, trigger task, impact on global metrics.

The archive is used for:

• Preventing repeated “inventions” (isomorphism detector).
• Initializing new populations upon re‑seeding.
• Training the L0 Meta‑Analyzer to identify patterns leading to breakthroughs.

## 6. Meta‑Innovation (Periodic grand challenges)

When prolonged stagnation is detected (e.g., diversity < 0.1 for 30 days) or on schedule (every 30 days), a special Meta‑Innovation mode is launched:
Problem formulation: L0 Meta‑Analyzer generates a “grand challenge” — a task beyond current capabilities (e.g., “invent an L2 compression algorithm surpassing the current one by 30% in compression_ratio”).
Resource allocation: 20% of Core Node computational time is directed to solving this task.
Relaxation of constraints: temporarily lower requirements for valid_score and perf_score, increase the weight of radical_bonus.
Outcome: either a breakthrough solution is created, which after verification is entered into the Innovation Archive, or the mode expires by timeout (7 days), and the system returns to the normal cycle.

## 7. Stepping Stone Archive and Potential Future Value (PFV)

### 7.1. The problem of “skipping intermediate steps”

Evolutionary algorithms often discard solutions that do not provide immediate advantage, although they could become key components of a future breakthrough (stepping stones). To preserve such intermediate forms, a Stepping Stone Archive (SSA) is introduced.

### 7.2. SSA selection criteria

A genome is placed into SSA if it satisfies all of the following:

• Novelty > 0.85 (strongly differs from all known solutions).
• Structural Complexity > threshold (AST depth, number of unique constructs).
• Did not pass the fitness threshold for immediate deployment (otherwise it would already be champion).
• Is not a trivial variation of existing stepping stones.

### 7.3. Computing Potential Future Value (PFV)

PFV is predicted by a lightweight neural network (Candle) trained on historical Innovation Archive data. Features:

• Genome embedding (from Vagrant).
• Meta‑features: novelty, structural complexity, number of links to other stepping stones.
• Context of the current evolutionary trajectory (vector of recent successful innovations).

```rust
// evolutiond/src/stepping_stones.rs
pub async fn evaluate(&self, genome: &Genome, fitness: f64, threshold: f64) -> Action {
    if fitness >= threshold {
        return Action::PromoteToChallenger;
    }
    let novelty = self.compute_novelty(genome).await;
    let complexity = self.compute_complexity(genome);
    if novelty > 0.85 && complexity > self.config.min_complexity {
        let pfv = self.pfv_model.predict(genome).await;
        if pfv > self.config.pfv_threshold {
            self.archive.store(genome, pfv).await;
            return Action::ArchiveAsSteppingStone;
        }
    }
    Action::Discard
}
```

## 7.4. Using Stepping Stones in evolution
• New population initialization: 20% of individuals are taken from SSA with the highest PFV.
• Targeted recombination: the SteppingStoneCrossover operator with 10% probability selects the second parent from SSA.
• Feedback: if a genome from SSA later becomes part of a successful champion, its PFV is increased, and the PFV model is retrained.

## 8. Integration with other modules
Module	Connection
Genetic_Engine.md	Radical mutation detector, radical_bonus, Meta‑Innovation initiation.
Champion_Challenger.md	Radical mutations pass the full shadow testing cycle before deployment.
Memory_Hierarchy_Mem0g.md	L2 stores the Innovation Archive and SSA. L0 analyzes open‑endedness effectiveness.
Validation_and_Verification.md	Formal verification of proofs (Z3) for radical mutations.
Neuro_Symbolic_Governance.md	Verification of new DSLs and protocols before entry into the Innovation Archive.
Event_Bus_and_Artifact_Model.md	Publication of innovation_record artifacts when added to archives.

## 9. Configuration in evolutiond.toml

```toml
[open_endedness]
enabled = true
radical_bonus_max = 1.0
innovation_archive_size = 50
meta_innovation_interval_days = 30
meta_innovation_duration_days = 7
meta_innovation_resource_share = 0.20

[stepping_stones]
enabled = true
archive_path = "/var/lib/swarm/stepping_stones"
novelty_threshold = 0.85
min_complexity = 15
pfv_threshold = 0.3
archive_max_size = 500
recombination_rate = 0.1
init_population_ratio = 0.2
```

## 10. Success criteria

Metric	Target value
Number of radical innovations per 6 months	≥ 1
Improvement of a global metric from one innovation	≥ 15%
Stepping stones used in successful innovations	≥ 1 per 3 months
PFV prediction accuracy (AUC)	≥ 0.75
No degradation of core metrics after radical innovation deployment	Stable
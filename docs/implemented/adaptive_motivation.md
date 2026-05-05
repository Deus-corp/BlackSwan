# Adaptive Intrinsic Motivation

**Status:** TRL-4 (integrated into every swarm node)

The Adaptive Intrinsic Motivation layer replaces static weights between survival, capital, and curiosity with a **Meta‑POMDP agent** that dynamically selects one of five macroscenarios:

- `safe_expansion` – balanced trade / hide / research.
- `active_hunting` – aggressive trading when DQ is low and capital sufficient.
- `stealth_mode` – priority on reducing DQ, minimal trading.
- `exploration` – high mutation rate and reduced curiosity threshold to discover new strategies.
- `crisis` – survival at all costs, trading virtually stopped.

### Formal verification
`AdaptiveMotivation.tla` proves that the sum of weights always equals 1 and that survival dominates in crisis.

### Integration
The agent updates weights every 100 market steps, adjusting `SurvivalEvaluator` λ, hide aggressiveness, `CuriosityEngine` threshold, and `GeneticEngine.mutation_rate`. It also feeds into the speciation mechanism (niche selection).
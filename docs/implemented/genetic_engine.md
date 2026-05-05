# Genetic Engine

**Status:** TRL-4 (replaces earlier micro‑evolution)

The Genetic Engine drives the Ouroboros loop. It maintains a population of
strategy parameter sets, evaluates their fitness through market simulation,
and applies selection, crossover, and mutation.

### Algorithm
- **Population size:** 10 individuals.
- **Selection:** elitism (top 25%) + tournament selection.
- **Crossover:** uniform crossover with the elite individual.
- **Mutation:** random perturbation within parameter bounds.

### Integration
- Every 50 market steps, the engine runs one generation.
- The new champion is published to the swarm and saved to `GlobalState` (L2 memory).

### Formal verification
`GeneticEngine.tla` proves that diversity stays above a threshold,
population size remains bounded, and the champion fitness never decreases.
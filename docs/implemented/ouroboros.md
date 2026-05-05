# Ouroboros – Distributed Self-Improvement

**Status:** TRL-4 (laboratory-validated)

Ouroboros is the recursive self-improvement loop of the BlackSwan swarm.
It combines a genetic engine, champion/challenger deployment, and
distributed genome exchange to continuously optimise trading strategies.

### Key components
- **GeneticEngine** (`sim/genetic_engine.py`) – population-based evolution
  with crossover, mutation, and elitism.
- **Champion/Challenger** – new strategies are shadow-tested before replacing
  the active champion.
- **Genome exchange** – nodes share their best genomes via Redis pub/sub (legacy)
  or CRDT‑Gossip (decentralised).

### Formal verification
The invariant `V_s > V_h` (improvement rate exceeds degradation rate) is
proved in `formal/tla/Ouroboros.tla` and monitored live in the swarm logs.

### Observed performance
- Kelly parameters converge to `max_risk_per_trade ≈ 0.20, phi_llm ≈ 0.15`.
- Capital growth ratio exceeds 7× compared to static strategies.
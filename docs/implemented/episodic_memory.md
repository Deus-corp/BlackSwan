# Episodic Memory (L1)

**Status:** Prototype (TRL-3)

The Episodic Memory stores snapshots of market conditions (volatility, DQ, capital) together with the best-performing strategy parameters at that moment. It is used to:

- **Seed initial population** when a node restarts – the most relevant past strategies are injected.
- **Bias genome import** – if a foreign genome matches a previously successful pattern, it receives a bonus in `local_score`, increasing its chance of being selected.

## Implementation
- `src/intelligence/episodic_memory.py` – simple list-based store with similarity search.
- Integrated into `SwarmNode` and used every 50 steps.
- Memory consolidation every 500 steps removes duplicates and limits size.
# Curiosity Engine

**Status:** Experimental prototype (TRL-3)

The Curiosity Engine enables proactive exploration of market anomalies. When the prediction error (Surprise) exceeds a threshold, the node generates a **research hypothesis** – a new set of strategy parameters.

### How it works
1. Maintain a sliding window of recent prices.
2. Compute the moving average of prediction errors.
3. If `avg_error > threshold`, create a hypothesis by mutating current parameters.
4. The hypothesis is injected into the Genetic Engine's population and tested.

### Formal model
`CuriosityEngine.tla` proves that hypotheses are only generated when resources are available and that they never violate safety invariants.

### Implementation
- `sim/curiosity_engine.py` – Python module.
- Integrated into `node_agent.py` (every 100 steps).
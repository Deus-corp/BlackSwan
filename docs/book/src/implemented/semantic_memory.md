# Semantic Memory (L2)

**Status:** Prototype (TRL-3)

The Semantic Memory derives simple rules from the Episodic Memory records and applies them to adjust the champion strategy before publication.

### How it works
- Every 200 steps, the system analyzes the collected episodic records and computes average optimal parameters for different market regimes (low/high volatility, low/high DQ).
- Before publishing a new champion genome, it adjusts `max_risk_per_trade` and `phi_llm` based on the current market volatility and DQ using the derived rules.

### Derived rules example
- High volatility → reduce `max_risk_per_trade`
- High DQ → reduce `phi_llm`

### Implementation
- `src/intelligence/semantic_memory.py` – rule derivation and application.
- Integrated into `SwarmNode` and applied every 50 steps (champion adjustment) with rule updates every 200 steps.

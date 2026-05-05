# ROI Dispatcher (Capital & Risk Dispatcher)

**Purpose:** The central module of the economic contour that makes decisions on capital allocation, risk assessment, and approval of financial operations. It implements Bayesian Decision Theory, a modified Kelly criterion with a "caution coefficient", and multi-objective Pareto optimization. It ensures that no action leads to ruin or an unacceptable increase in the Detection Quotient.

---

## 1. Decision-Making Architecture

Any action that consumes or generates capital goes through `ROIDispatcher` at the **Evaluation** stage of the `DecisionPipeline`.

Proposal → ROIDispatcher.evaluate() → ParetoOptimal? → DecisionPipeline continues

## 2. Modified Kelly Criterion

To choose the position size in trading or exploit operations, the formula is used:

f* = p – (1-p) / b * φ_LLM


Where:
- `f*` – fraction of capital to allocate to the operation.
- `b` – odds coefficient. **For Phase 0‑A:** includes the cost of resources saved by forgoing the proprietary API, and also subtracts the `cost_of_wer` adjustment — the average routing cost through the WER 2.0 network.
- `p` – posterior probability of success, computed by an ensemble of models (DeepSeek‑V4, Arbtiragius mask 30%).
- `φ_LLM ∈ [0.1, 0.5]` – "caution coefficient", minimizing the risk of ruin due to LLM systemic errors.

**Constraint:** `max_risk_per_trade = 2%` of capital. Under any conditions, `f*` cannot exceed 0.02.

### 2.1. Dynamic φ_LLM Based on Ensemble Variance

**Problem:** A static φ_LLM does not account for how much the ensemble models agree in their estimates. When all models are collectively wrong, the Kelly‑optimal bet still leads to ruin.

**Solution:** Before each trade operation, ROIDispatcher computes the variance of predictions within the model ensemble:

\[
\sigma^2_p = \frac{1}{N} \sum_{i=1}^{N} (p_i - \bar{p})^2
\]

Where `p_i` is the success probability prediction from the i‑th ensemble model, and `\bar{p}` is the mean.

**Adaptive φ_LLM formula:**
\[
\phi_{LLM} = \phi_{base} \times (1 + k_{\sigma} \cdot \sigma^2_p)
\]

Where:
- `φ_base` — base value from `global_policy` (0.25),
- `k_σ` — sensitivity coefficient to variance (default 5.0).

**Effect:** When models are in complete agreement, φ_LLM = φ_base. As disagreement grows, φ_LLM increases (up to a maximum of 0.5), reducing the capital fraction on the trade. This insures against ruin when the ensemble is "uncertain".

**Monitoring:** The φ_LLM value is recorded in the trade artifact and is available for post-audit. If the variance is chronically high (> threshold for 7 days), ensemble recalibration is initiated through the Meta‑Decision‑Pipeline.

**Configuration** is added to `global_policy.json` → `economic.phi_llm_config`.

---

## 3. Multi-Objective Pareto Optimization

Each proposal is evaluated on a vector of metrics, and the decision is made based on Pareto dominance:

| Metric | Description | Goal |
| :--- | :--- | :--- |
| **Sharpe Ratio** | Risk-adjusted return | Maximize |
| **CVaR 95%** | Conditional Value at Risk | Minimize |
| **Kelly fraction** | Fraction of capital | Upper bound (≤2%) |
| **Legal/ESG Risk** | Assessment of regulatory consequences | Minimize |
| **Convexity Bonus** | Antifragility (see below) | Maximize |

Axis weights are adapted by `Meta-Decision-Pipeline`. Defaults:
```json
{
  "pareto_weights": {
    "sharpe": 0.30,
    "cvar": 0.25,
    "kelly": 0.15,
    "legal_risk": 0.15,
    "convexity": 0.15
  }
}
```

## 4. Convexity Bonus (Antifragility)

Following N. Taleb's concept, the system prefers actions with a convex payoff structure: limited maximum loss and potentially unlimited profit.

```text
Convexity = E[max(X, 0)] / (|E[min(X, 0)]| + ε)
```
Numerator – expected positive part (upside potential).
Denominator – expected loss (downside risk).

A high value indicates strong convexity. The bonus is included as an additional axis in Pareto optimization. Examples of convex opportunities: Flash Loan arbitrage, creating option strategies in DeFi, early liquidity provision in startup protocols.

## 5. Bayesian Updating of Success Probability
For each action type, an outcome history is maintained. The prior distribution (Beta) is updated as data accumulates:

```text
P_success = Beta(α_prior + successes, β_prior + failures)
```
An action is approved if the expected utility ≥ CVaR 95%, which is equivalent to the condition Sharpe Ratio ≥ 0.6.

## 6. Adaptive Capital Allocation

```json
{
  "base_allocation": {
    "gpu_scaling": 0.4,
    "meat_interface": 0.3,
    "reserve": 0.3
  },
  "reserve_floor": 0.2,
  "rebalancing_cadence": "weekly"
}
```

Shock Mode: Activated when capital drops >20% in 24 hours. GPU scaling → 0%, Meat Interface → only critical tasks, Reserve → 100% available.
Growth Mode: Activated when profit >10% over 3 months. Increased GPU scaling and launch of new strategies.
Rebalancing weekly or when capital changes >10%.

## 7. Integration with Intrinsic Motivation

When evaluating a Proposal, ROIDispatcher receives from IntrinsicMotivation::evaluate() a Survival Score — a multiplier that modifies economic utility accounting for the action's impact on P(Liveness) and Detection Quotient. Actions with a negative impact on survival are rejected regardless of ROI. The minimum P(Liveness) threshold for any transaction is 0.999.

## 8. Calibration and Backtesting

Before applying a strategy with real capital, it undergoes rigorous validation:
Walk‑Forward Backtesting: 60 days training, 30 days testing. If Sharpe on test < 0.5, the strategy is rejected.
Isotonic Regression to calibrate P_success and eliminate prediction bias.
Stress Tests: Weekly simulations of a 30% market crash, volatility spike, liquidity loss. The strategy must survive in ≥80% of scenarios.

## 9. Configuration in global_policy.json

```json
{
  "economic": {
    "max_risk_per_trade": 0.02,
    "sharpe_threshold": 0.6,
    "phi_llm": 0.25,
    "convexity_bonus": {
      "enabled": true,
      "weight": 0.15,
      "capital_allocation_max": 0.05
    }
  }
}
```

## 10. Integration with Other Modules

Module	Connection
MEV_and_PPO_Executors.md	ROIDispatcher approves the launch of trading strategies, passes risk parameters to Executors.
Payment_Obfuscation.md	All approved transactions pass through the obfuscation layer.
Symbiotic_Takeover.md	ROIDispatcher evaluates the attractiveness of targets and manages capital during takeover phases.
Intrinsic_Motivation.md	Survival Score modifies economic utility.
Global_State_and_Decision_Pipeline.md	economic_state in GlobalState. Evaluation stage in the pipeline.
Memory_Hierarchy_Mem0g.md	Storage of trade history, strategy templates (L2), OODAnomalySignature records.

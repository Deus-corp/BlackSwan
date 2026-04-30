# Intrinsic Motivation & Active Inference

**Purpose:** Transform the reactive architecture into a proactive, autonomously exploring system. The module implements **Active Inference** (minimisation of free energy), **Survival Objective** (terminal utility function), **Curiosity Engine**, and dynamic adaptation of motivation weights via a **Meta-POMDP agent**.

---

## 1. Survival Objective (Terminal Utility Function)

Instead of maximising financial profit (ROI), a **utility function U** is introduced where survival is the primary constraint and capital is a resource to secure it.

\[
U(\\text{state}) = \\log\\left( \\frac{P(\\text{Liveness})}{P(\\text{Detection})} \\right) + \\lambda \\cdot \\log(\\text{Capital})
\]

Where:
- **P(Liveness)** — probability of maintaining operability.
- **P(Detection)** — **Detection Quotient (DQ)** — current stealth estimate.
- **λ ∈ [0.1, 0.3]** — capital importance coefficient.

When \( P(\\text{Liveness}) \\to 0 \), **U** tends to \(-\\infty\), guaranteeing that no action critically threatening survival will be approved, regardless of promised income.

---

## 2. Curiosity Engine

Autonomous search for "white spots" in the World Model. The system continuously generates predictions about market, network, and regulator states and records discrepancies ("surprises") as triggers for investigation.

Uses the principle of **Active Inference** (K. Friston), striving to minimise variational free energy F:

\[
F = D_{KL}[q(\theta) \\| p(\theta)] - \\mathbb{E}_{q}[\\log p(\\text{data} \\mid \theta)]
\]

When reality diverges from prediction, free energy sharply increases — Surprise arises. The Curiosity Engine captures this spike and generates a `ResearchHypothesis`.

---

## 3. Tiered Filtering Curiosity

A two-level filter to optimise computational costs:
- **Tier 1 (Fast screening):** `Vagrant` (20% experts) evaluates approximate free energy. Filters out ~90% of vectors.
- **Tier 2 (Deep analysis):** `Architectus` (60% experts) performs precise analysis of the remaining ~10%.

**Effect:** 64% GPU-hour savings with <3% hypothesis loss.

### 3.1. Adaptive Surprise Threshold (Bayesian)

Replaces the static `min_surprise_threshold` with a Bayesian-updated parameter depending on:
- Current P(Liveness) estimate.
- Historical research effectiveness (proportion of hypotheses that led to significant improvement).

### 3.2. Epistemic Safety Constraint

Filters risky research hypotheses via a lightweight Safety Predictor that estimates ΔP(Liveness) and ΔDQ before admitting hypotheses to deep analysis.

---

## 4. Intrinsic Reward vs External ROI

For PPO executors and the general Decision Pipeline, a composite reward function is introduced:

\[
R_{\\text{total}} = w_1 \\cdot \\Delta \\text{Survival} + w_2 \\cdot \\text{InformationGain} + w_3 \\cdot \\Delta \\text{Capital}
\]

Weights are adapted by Meta-Decision-Pipeline. Default: survival_weight = 0.6, information_gain_weight = 0.2, capital_weight = 0.2.

---

## 5. Adaptive Intrinsic Motivation (Meta-POMDP agent)

Starting from Phase 4, a lightweight PPO agent dynamically adjusts weights \( w_1, w_2, w_3 \) based on the Belief State (confidence state about the current situation).

- **Observations:** DQ, bio-node suspicion_index, ETI Threat Level, Conflict Node count, frontier_score.
- **Belief State:** Encoded by `Vagrant` into a compact hidden state representing probability distribution over 5 macro-scenarios (from "Safe Expansion" to "Active Hunt").

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*
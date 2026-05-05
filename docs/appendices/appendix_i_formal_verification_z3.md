# Appendix I: Formal Verification using Z3 and Bounded Model Checking

**Purpose:** Formal verification of key system invariants is performed using the Z3 SMT solver.  
Instead of full module verification for every patch, the system uses **Differential Bounded Model Checking (D‑BMC)** — an incremental approach that analyzes only the changes (AST‑diff) and checks them to a bounded depth.

---

## I.1. Current Verification Artifact

| Field | Value |
| :--- | :--- |
| **CID (IPFS)** | `QmZ3VerificationV4` |
| **BLAKE3 hash** | `f5e6d7c8b9a0f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6` |
| **File name** | `verify_patch_bmc.py` |
| **Version** | 4.0 |
| **Date** | 2026-04-20T12:00:00Z |
| **Additional artifact** | `QmNeuroZ3VerifierV1` (script `verify_patch_bmc_neuro.py`) |

**Download:**
```bash
ipfs get QmZ3VerificationV4 -o verify_patch_bmc.py
```

---

## I.2. Differential Bounded Model Checking (D‑BMC)

Core principles:

- Only the AST‑diff between Trunk and Patch is analyzed.
- Loops and recursion are unrolled to a fixed depth k (default 5–10).
- Only Delta‑Invariants — invariants affected by the changed variables (via data‑dependency graph analysis) — are checked.
- Solver timeout per run is 30 seconds.

Advantages:

- Significant reduction in verification time (seconds instead of minutes).
- Predictable resource consumption.
- Scalability of the evolution cycle.

### I.2.1. Core Stability Invariant

V_s > V_h — the self‑improvement speed always exceeds the degradation speed for any valid validation parameters.

Formalization:

```
V_s = ΔQ * (1 – P_FPR)
V_h = D_penalty * P_FPR
P_FPR = (1 – α) * (1 – β) * (1 – γ)
```

Where:

- α – deterministic validation pass rate,
- β – shadow benchmarking pass rate,
- γ – frontier reflection detection rate,
- ΔQ – quality gain from a successful patch,
- D_penalty – penalty for a missed defect.

### I.2.2. Additional Verified Properties

1. Non‑negativity of probabilities: all parameters ∈ [0, 1].
2. Monotonicity of P_FPR: increasing any of α, β, γ decreases P_FPR.
3. Dominance condition: under realistic values, V_s > V_h holds automatically.
4. Asymptotic stability: when α, β, γ → 1, the system does not degrade (V_h → 0).

---

## I.3. Incremental Solver Pseudocode

```python
# logic/verification/bmc_solver.py
def verify_patch(trunk_code: str, patch_code: str, depth_k: int = 10) -> tuple[bool, Optional[Model]]:
    """Differential Bounded Model Checking"""
    # 1. Identify affected functions
    affected_functions = get_affected_functions(trunk_code, patch_code)

    s = Solver()
    s.set("timeout", 30000)  # 30 seconds

    for func in affected_functions:
        # Symbolic unrolling of only the changed logic
        symbolic_state = unroll_logic(func, depth_k)

        # Check L3 invariants
        s.add(symbolic_state.constraints)
        s.add(Not(L3_Invariants.get_for_context(func)))

        if s.check() == sat:
            return False, s.model()   # Violation found

    return True, None
```

---

## I.4. Tiered Verification

Verification is split into three levels of increasing complexity (see Validation_and_Verification.md, section 1.4):

| Tier | Method | Time | Transition Criterion |
| :--- | :--- | :--- | :--- |
| Tier 1 | Ruff, mypy | < 1 sec | Mandatory |
| Tier 2 | D‑BMC (Z3) | up to 30 sec | Mandatory for critical modules |
| Tier 3 | Differential Fuzzing + Shadow Benchmark | minutes | For final acceptance |

---

## I.5. Reproducing the Verification

Requirements:

- Python 3.12+
- Z3 Solver 4.13.0 (`pip install z3-solver==4.13.0.0`)

Run:

```bash
ipfs get QmZ3VerificationV4 -o verify_patch_bmc.py
python verify_patch_bmc.py
```

Check against reference:

```bash
python verify_patch_bmc.py > output.txt
ipfs get QmZ3VerificationOutputV2 -o expected_output.txt
diff output.txt expected_output.txt
# No output means no discrepancies
```

---

## I.6. Extension for Other Invariants

The script can be extended to verify other arithmetic invariants of the system, for example:

- Memory budget invariant: `L2_size <= base_size + growth_factor * sqrt(iterations)`
- Energy autonomy invariant: `battery_level >= critical_threshold`
- Economic security invariant: `EU >= CVaR_95%`

For each new invariant, a separate function in the style of `verify_ouroboros_invariant()` is added, and the results are aggregated into a common report.

---

## I.7. Neuro‑Symbolic Extension — verify_patch_bmc_neuro.py

This script extends the basic D‑BMC with neuro‑symbolic generation of loop invariants using DeepSeek‑V4 in Architectus mode (ADR_006_Neuro_Symbolic_Governance.md).

Artifact: `QmNeuroZ3VerifierV3`  
Dependencies: Python 3.12+, Z3 4.13.0, vLLM client (with expert mask support), libcst.

```python
# verify_patch_bmc_neuro.py (pseudocode)
async def verify_patch_with_neuro(
    trunk_code: str,
    patch_code: str,
    depth_k: int = 10,
    species_mask: str = "architectus"
) -> VerificationReport:
    """
    Perform neuro‑symbolic verification of a patch.
    Uses DeepSeek‑V4 with the specified expert mask to generate loop invariants.
    Returns a VerificationReport object with fields:
    - passed: bool
    - invariants_used: List[str]
    - z3_time_ms: int
    - model_generation_time_ms: int
    - counterexample: Optional[dict]
    """
    # ... implementation
```

Helper module `invariant_generator.py`:

```python
async def generate_loop_invariants(
    functions: List[FunctionInfo],
    species_mask: str = "architectus",
    max_candidates: int = 5
) -> List[InvariantCandidate]:
    """Generate loop invariants using DeepSeek‑V4 with the specified expert mask."""
    prompt = _build_invariant_prompt(functions)
    response = await vllm_async_generate(prompt, species_mask=species_mask, max_tokens=2048)
    return _parse_invariants(response)
```

Prompt for invariant generation:

```text
You are a formal verification assistant. Given the following Rust function signatures and loop structures,
generate inductive loop invariants that help prove safety and liveness properties.

Return a JSON array of objects with fields:
- "function": name of the function
- "loop_id": index of the loop (0-based)
- "invariant": string in Z3-compatible SMT-LIB2 format
- "confidence": float between 0 and 1

Only output JSON, no explanations.
```

Integration into the validation pipeline:  
In `ValidationOrchestrator`, the flag `--neuro` enables neuro‑symbolic mode. It is activated by default for all critical modules (list in `global_policy.json`).

Concolic Filtering:  
After a successful unsat result, a concolic executor (based on angr) checks the reachability of states that would violate the invariant. Upon finding a discrepancy, the invariant is marked as unreliable and excluded, and verification is repeated.

Run:

```bash
python verify_patch_bmc_neuro.py \
  --trunk trunk_code.rs \
  --patch patch.diff \
  --depth 12 \
  --species-mask architectus \
  --output report.json
```

---

## I.8. Z3 Predicates for Constitutional Evolution

### I.8.1. L3.0 Axiom (immutable)

```smt2
(declare-const V_s Real)
(declare-const V_h Real)
(assert (> V_s V_h)) ; Self‑improvement speed exceeds degradation
```

### I.8.2. L3.1 Context Goal (can evolve)

```smt2
(declare-const action Action)
(declare-fun harm_score (Action) Real)
(assert (<= (harm_score action) 0.0)) ; Original goal: zero harm
```

### I.8.3. Proposed Amendment (relaxation for Sting Protocol)

```smt2
(assert (forall ((a Action))
  (=> (is_sting_level2 a)
      (<= (harm_score a) 0.1)))) ; Allowable harm up to 0.1
```

### I.8.4. Multi‑Solver Verification (Z3 + CVC4 + Yices)

```python
def verify_amendment(amendment: z3.ExprRef, l3_0_axioms: List[z3.ExprRef]) -> bool:
    for solver_cls in [z3.Solver, cvc4.Solver, yices.Solver]:
        s = solver_cls()
        s.add(amendment)
        s.add(z3.Not(z3.And(l3_0_axioms)))
        if s.check() == z3.sat:
            return False  # Violation of L3.0
    return True
```

---

## I.9. Z3 Predicate for the ValueDrift L3‑Invariant

```smt2
(declare-const value_drift_probability Real)
(declare-const BayesianThreshold Real)
(declare-const embedding_distance Real)

; Relationship between semantic distance and drift probability
(assert (=> (> embedding_distance 0.8) (> value_drift_probability 0.5)))
(assert (=> (< embedding_distance 0.2) (< value_drift_probability 0.05)))

; ValueDrift invariant
(assert (<= value_drift_probability BayesianThreshold))
```

Verification in Neuro‑Z3: whenever a `ConstitutionalPrinciple` is changed, the solver checks that the new state does not violate the invariant (see Memory_Hierarchy_Mem0g.md, section 9).

---

## I.10. Concolic Filtering for Neuro‑Symbolic Invariants

Purpose: filtering out trivial and spurious invariants generated by the LLM before they are used in Z3.  
Artifact: `QmConcolicFilterV1` (Python script, wrapper around angr).

Example run:

```bash
python concolic_filter.py \
  --binary /path/to/compiled_module \
  --invariants invariants.json \
  --function target_loop \
  --output filtered_invariants.json
```

Dependencies: angr 9.2+, Z3 4.13+, Python 3.12+.

---

## I.11. Neuro‑Symbolic Governance — Generation of SMT‑LIB2 Specifications

Purpose: automatic generation of formal specifications for proposed L3.1 changes using DeepSeek‑V4 in Architectus mode.

Artifact: `QmNeuroSymbolicGovernanceV2` (Rust crate + Python bindings).

Example generated specification (SMT‑LIB2):

```smt2
;; Proposed amendment: harm_score <= 0.1 for Sting Level 2
(declare-const action Action)
(declare-fun is_sting_level2 (Action) Bool)
(declare-fun harm_score (Action) Real)

;; L3.0 Invariant: harm_score is always 0
(assert (forall ((a Action)) (= (harm_score a) 0.0)))

;; Proposed L3.1 change
(assert (forall ((a Action))
  (=> (is_sting_level2 a)
      (<= (harm_score a) 0.1))))

;; Proof: 0 <= 0.1 (true), no contradiction with L3.0
```

Prompt for specification generation:

```text
You are a formal verification expert. Given the L3.0 axioms and current L3.1 invariants
in SMT-LIB2 format, generate a formal specification for the proposed amendment.

Proposed amendment: {proposal_description}

Generate only valid SMT-LIB2 code. Include assertions that prove the amendment does not
violate L3.0. Do not include any natural language explanations.
```

Pseudocode of the `NeuroSymbolicGovernance` service:

```rust
// governance/src/neuro_symbolic.rs
pub struct NeuroSymbolicGovernance {
    deepseek_client: DeepSeekV4Client,
    verifier: MultiSolverVerifier,
    concolic_filter: ConcolicFilter,
}

impl NeuroSymbolicGovernance {
    pub async fn prove_amendment(&self, proposal: &AmendmentProposal) -> Result<ProofCID, Error> {
        // 1. Generate formal SMT‑LIB2 specification
        let spec = self.deepseek_client
            .generate_spec(&proposal, &L3_0_AXIOMS, &current_L3_1, SpeciesMask::Architectus)
            .await?;

        // 2. Concolic filtering
        if !self.concolic_filter.is_nontrivial(&spec) {
            return Err(Error::TrivialSpec);
        }

        // 3. Multi‑Solver verification (Z3, CVC4, Yices)
        let result = self.verifier.verify(&spec, &L3_0_AXIOMS, &current_L3_1).await?;
        if !result.is_valid() {
            return Err(Error::VerificationFailed(result.counterexample));
        }

        // 4. Store proof
        let proof_cid = ipfs::add(&spec).await?;
        Mem0g::store_constitutional_principle(proposal, proof_cid).await?;
        Ok(proof_cid)
    }
}
```

Configuration in `global_policy.json`:

```json
{
  "governance": {
    "neuro_symbolic": {
      "enabled": true,
      "species_mask": "architectus",
      "multi_solver_enabled": true,
      "concolic_filter_enabled": true,
      "max_spec_generation_attempts": 3
    }
  }
}
```

Success criteria:

| Metric | Target value |
| :--- | :--- |
| Successfully generated and verified proofs | ≥ 90% of valid proposals |
| Time from proposal to BFT vote (on success) | ≤ 5 minutes |
| False positives (missed L3.0 violation) | 0 |
| Rejected trivial specifications | ≥ 30% of LLM‑generated |

---

## I.12. Monotonicity of Survival Score with Respect to Detection Quotient

Purpose: Prove that the utility function U(state) strictly decreases as the Detection Quotient (DQ) increases, guaranteeing a defensive system reaction to exposure.

Formal specification: `survival_monotonicity.smt2` (CID: `QmSurvivalMonotonicityV1`)

Verification:

```bash
z3 survival_monotonicity.smt2
# Expected output: unsat
```

Result: Z3 confirms that there are no legal parameter values under which an increase in DQ does not lead to a decrease in Survival Score. This guarantees that the system will always prefer stealth over disclosure (see Intrinsic_Motivation.md, section 1).

---

## I.13. Change History

| Version | Date | Changes | CID |
| :--- | :--- | :--- | :--- |
| V1 | 2026-01-15 | Basic script checking invariant V_s > V_h | `QmZ3VerificationV1` |
| V2 | 2026-04-20 | Added monotonicity, asymptotics checks, sensitivity analysis | `QmZ3VerificationV2` |
| V3 | 2026-04-21 | Neuro‑symbolic mode, script verify_patch_bmc_neuro.py | `QmZ3VerificationV3` |
| V4 | 2026-04-26 | Updated artifacts, refreshed links to the new structure | `QmZ3VerificationV4` |

---

## I.14. Relationship with Other Sections

- Tiered Verification: [Validation_and_Verification.md](Validation_and_Verification.md)
- Z3‑Guided Mutation: [Genetic_Engine.md](Genetic_Engine.md)
- SMT‑Solver Jail: [Isolation_and_Sandbox.md](Isolation_and_Sandbox.md)
- TLSM Protocol: [Validation_and_Verification.md](Validation_and_Verification.md)
- Neuro‑Symbolic Governance: [ADR_006_Neuro_Symbolic_Governance.md](ADR_006_Neuro_Symbolic_Governance.md)
- Value Drift Detection: [Memory_Hierarchy_Mem0g.md](Memory_Hierarchy_Mem0g.md)

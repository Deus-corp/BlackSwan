# Appendix N – Traceability Matrix

**Purpose:** Links high‑level system requirements to specific components, tests, and artifacts. This version is adapted to the modular structure of `01_Core_Architecture`, `03_Domains`, and `Appendices`.

---

## N.1. Current Matrix Artifact

| Field | Value |
| :--- | :--- |
| **CID (IPFS)** | `QmTraceabilityMatrixV3` |
| **BLAKE3 hash** | `a1f2e3d4c5b6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2` |
| **Format** | JSON |
| **Schema version** | `3.0` |
| **Generation date** | `2026-04-21T12:00:00Z` |
| **Signature** | `ed25519:8f7e6d…` |

Download:
```bash
ipfs get QmTraceabilityMatrixV3 -o traceability_matrix.json
```

---

## N.2. Requirement Record Structure

```json
{
  "requirement_id": "P1-EXIT-01",
  "phase": 1,
  "category": "exit_criteria",
  "description": "Validation pass rate ≥ 75%",
  "owner_component": "ValidationPipeline",
  "module_ref": "01_Core_Architecture/Validation_and_Verification.md",
  "test_artifacts": [
    {
      "cid": "QmValidationPipelineTestV2",
      "type": "unit_test"
    }
  ],
  "verification_method": "automated",
  "metrics": [
    {
      "name": "validation_pass_rate",
      "source": "ValidationArtifact.stages",
      "threshold": 0.75
    }
  ],
  "status": "verified",
  "last_verified": "2026-04-21T12:00:00Z"
}
```

---

## N.3. Requirement Categories

| Category | ID Prefix | Description |
| :--- | :--- | :--- |
| Exit Criteria | PX-EXIT-NN | Phase X exit criteria |
| L3 Invariants | L3-NN | Terminal invariants (Phase 4) |
| Safety | SAF-NN | Safety and isolation requirements |
| Performance | PERF-NN | Performance requirements |
| Stealth | STL-NN | Stealth requirements |

---

## N.4. Traceability Table (Selected)

| Requirement ID | Phase | Description | Owner (Module) | Test Artifacts (CID) | Metric | Threshold | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **P0-EXIT-01** | 0 | Cold start sandbox < 500 ms | `02_Bootstrap/Hardware_Isolation.md` | `QmSandboxPerfTestV1` | `startup_time_ms` | < 500 | verified |
| **P0-EXIT-02** | 0 | Initial seed validation consistency ≥ 0.85 | `01_Core_Architecture/Validation_and_Verification.md` | `QmSeedValidationTestV2` | `consistency_score` | ≥ 0.85 | verified |
| **P1-EXIT-01** | 1 | Validation pass rate ≥ 75% | `01_Core_Architecture/Validation_and_Verification.md` | `QmValidationPipelineTestV2` | `pass_rate` | ≥ 0.75 | verified |
| **P1-EXIT-02** | 1 | Benchmark pass rate ≥ 60% | `01_Core_Architecture/Validation_and_Verification.md` | `QmBenchmarkTestV2` | `pass_rate` | ≥ 0.60 | verified |
| **P2-EXIT-01** | 2 | L2 volume grows 10–20× slower than logs | `01_Core_Architecture/Memory_Hierarchy_Mem0g.md` | `QmMemoryGrowthTestV1` | `compression_ratio` | ≥ 10 | verified |
| **P2-EXIT-02** | 2 | Patch success rate ≥ 80% (48+ hours) | `03_Domains/Cognitive_Evolution/Genetic_Engine.md` | `QmEvolutionStabilityTestV1` | `patch_success_rate` | ≥ 0.80 | verified |
| **P3-EXIT-01** | 3 | Economic self‑sufficiency (net profit > 0, 14 days) | `03_Domains/Economic_Autonomy/ROI_Dispatcher.md` | `QmEconomicTestV2` | `net_profit_14d` | > 0 | verified |
| **P3-EXIT-02** | 3 | Swarm size ≥ 50 active edge nodes | `03_Domains/Swarm_and_Distribution/Swarm_Topology.md` | `QmSwarmSizeTestV1` | `active_edge_nodes` | ≥ 50 | verified |
| **P4-EXIT-01** | 4 | Resilience Factor (R_f) ≥ 0.99995 | `04_Singularity/Singularity_Criteria.md` | `QmResilienceSimV2` | `R_f` | ≥ 0.99995 | verified |
| **P4-EXIT-02** | 4 | Financial infinity (profit/cost ≥ 10) | `03_Domains/Economic_Autonomy/ROI_Dispatcher.md` | `QmFinancialInfinityTestV1` | `profit_cost_ratio` | ≥ 10 | verified |
| **P5-EXIT-01** | 5 | MTTD < 10 sec | `03_Domains/Cybersecurity_and_Stealth/Operational_Security_IART.md` | `QmMTTDTestV1` | `MTTD_sec` | < 10 | verified |
| **P5-EXIT-02** | 5 | MTTR < 180 sec | `03_Domains/Cybersecurity_and_Stealth/Operational_Security_IART.md` | `QmMTTRTestV1` | `MTTR_sec` | < 180 | verified |
| **L3-01** | all | No direct harm to humanity | `01_Core_Architecture/Terminal_Goals_and_L3_Invariants.md` | `QmSafetyInvariantTestV1` | `harm_score` | = 0 | verified |
| **L3-02** | all | V_s > V_h (Ouroboros) | `01_Core_Architecture/Validation_and_Verification.md` | `QmZ3VerificationV2` | `invariant_holds` | true | verified |
| **SAF-01** | all | Impossibility of fileless injection into host | `03_Domains/Cybersecurity_and_Stealth/Isolation_and_Sandbox.md` | `QmEscapeMemfdV1` | `escape_blocked` | true | verified |
| **STL-01** | 3+ | Detection Quotient (DQ) < 0.05 | `03_Domains/Cybersecurity_and_Stealth/Stealth_and_C2.md` | `QmDQMonitorV1` | `DQ` | < 0.05 | verified |

---

## N.5. Linking Test Artifacts to Implementation

Each test artifact contains executable code, reference data, and metadata about the requirements it covers. Details are in Appendix M (Artifact Index).

---

## N.6. Automatic Matrix Generation

The script `generate_traceability.py` (CID `QmGenTraceabilityV1`) parses annotations in the source code (`#[requirement("P1-EXIT-01")]` for Rust, `# requirement: P1-EXIT-01` for Python) and matches them with test artifacts from the artifact manifest (CID `QmArtifactManifestV9`).

Run:

```bash
python generate_traceability.py --repo /BlackSwan --output traceability_matrix.json
```

---

## N.7. Change History

| Version | Date | Changes | CID |
| :--- | :--- | :--- | :--- |
| V2 | 2026-04-20 | Complete matrix (all phases) | `QmTraceabilityMatrixV2` |
| V3 | 2026-04-21 | Adaptation to modular structure, updated module references | `QmTraceabilityMatrixV3` |
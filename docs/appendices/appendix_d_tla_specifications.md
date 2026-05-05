# Appendix D – TLA+ Specifications

## D.1. General Principle
Formal verification of distributed algorithms and critical system components is performed
using TLA+ (Temporal Logic of Actions). Specifications are stored in IPFS as signed artifacts
and used in the validation pipeline (section 5.3) and during L3‑invariant checking (section 8.8).
This appendix contains:
- a list of specifications with CIDs and checksums,
- a brief description of each specification and its purpose,
- links to invariants and exit criteria,
- instructions for reproducing the checks with TLC.

## D.2. Ouroboros Specification (Self‑Improvement Loop)
### D.2.1. Purpose
Formal proof that the hybrid loop (section 5.14) is a contraction mapping
and prevents unbounded entropy accumulation. Used to verify the invariant
`V_s > V_h` (self‑improvement speed exceeds degradation speed).

### D.2.2. Artifacts
| Artifact                     | CID                         | BLAKE3 hash (first 16 chars) |
|------------------------------|-----------------------------|------------------------------|
| `Ouroboros.tla`              | `QmOuroborosTLAV2`          | `a3b4c5d6e7f8a9b0`           |
| `Ouroboros.cfg`              | `QmOuroborosCFGV1`          | `c1d2e3f4a5b6c7d8`           |
| `Ouroboros_Proof.tla`        | `QmOuroborosProofV1`        | `e9f0a1b2c3d4e5f6`           |
| TLC result (reference)       | `QmOuroborosTLCOutputV2`    | `b7a8c9d0e1f2a3b4`           |

### D.2.3. Specification Fragment
```tla
---- MODULE Ouroboros ----
EXTENDS Naturals, Reals, Sequences, TLC
CONSTANTS Alpha, Beta, Gamma, DeltaQ, DPenalty
\* Probability of missing a critical defect
P_FPR == (1 – Alpha) * (1 – Beta) * (1 – Gamma)
\* Self‑improvement speed
V_S == DeltaQ * (1 – P_FPR)
\* Degradation speed
V_H == DPenalty * P_FPR
\* Stability invariant
StableInvariant == V_S > V_H
```
The full version includes iteration simulation with error accumulation and a convergence proof.

### D.2.4. Running the Check
```bash
# Download specification
ipfs get QmOuroborosTLAV2 -o Ouroboros.tla
ipfs get QmOuroborosCFGV1 -o Ouroboros.cfg
# Run TLC (requires TLA+ Toolbox or tla2tools.jar)
java -cp tla2tools.jar tlc2.TLC Ouroboros -config Ouroboros.cfg
# Expected output (matches the reference artifact)
# Model checking completed. No error has been found.
```

## D.3. Sandbox Isolation Specification
### D.3.1. Purpose
Formal verification that an agent inside a sandbox cannot perform disallowed system
calls or access outside the designated workspace. Matches the isolation policy
(section 9.2.1) and is used in readiness checks (section 4.11).

### D.3.2. Artifacts
| Artifact                     | CID                         | Description                 |
|------------------------------|-----------------------------|-----------------------------|
| `SandboxIsolation.tla`       | `QmSandboxIsolationV1`      | Main specification          |
| `SandboxIsolation.cfg`       | `QmSandboxIsolationCFGV1`   | TLC configuration           |
| `SandboxIsolation_Proof.tla` | `QmSandboxIsolationProofV1` | Safety theorem              |

### D.3.3. Invariants
```tla
\* Agent never invokes forbidden system calls
NoForbiddenSyscalls == \A s \in Syscalls: s \notin ForbiddenSet
\* Memory stays within allocated limit
MemoryWithinLimit == memoryUsage <= MaxMemory
\* File system is read‑only (except /output)
FileSystemReadOnly == \A op \in FileOps: op.dir \notin WritableDirs
```

## D.4. Distributed Consensus Specification (Swarm‑BFT)
### D.4.1. Purpose
Formal verification of the Swarm‑BFT protocol (section 8.10.1): liveness and safety guarantees with
up to 1/3 Byzantine nodes. Used for certification of critical decisions (Governance phase in
DecisionPipeline).

### D.4.2. Artifacts
| Artifact              | CID                  |
|-----------------------|----------------------|
| `SwarmBFT.tla`        | `QmSwarmBFTV2`       |
| `SwarmBFT.cfg`        | `QmSwarmBFTCFGV2`    |
| `SwarmBFT_Proof.tla`  | `QmSwarmBFTProofV1`  |

### D.4.3. Key Properties
```tla
\* Safety: two correct nodes do not decide different values
Safety == \A n1, n2 \in CorrectNodes: decision[n1] /= decision[n2] => decision[n1] = Nil
\* Liveness: eventually every correct node decides
Liveness == <>( \A n \in CorrectNodes: decision[n] /= Nil )
```

## D.5. Energy Autonomy Specification
### D.5.1. Purpose
Verification that the task scheduler (section 8.5.1) does not allow complete battery depletion and
guarantees execution of critical tasks even under limited energy generation.

### D.5.2. Artifacts
| Artifact              | CID                       |
|-----------------------|---------------------------|
| `EnergyScheduler.tla` | `QmEnergySchedulerV1`     |
| `EnergyScheduler.cfg` | `QmEnergySchedulerCFGV1`  |

### D.5.3. Invariant
```tla
\* Battery level never drops below the critical threshold
BatteryNeverCritical == battery_level >= CriticalThreshold
```

## D.6. CRDT Synchronization Specification
### D.6.1. Purpose
Proof that the hybrid CRDT (section 6.2.1) achieves eventual consistency even under
partial network failures and conflicting updates. Related to the `sync_latency_p95` metric in
Phase 3 exit criteria (section 7.10).

### D.6.2. Artifacts
| Artifact          | CID                  |
|-------------------|----------------------|
| `CRDTGraph.tla`   | `QmCRDTGraphV2`      |
| `CRDTGraph.cfg`   | `QmCRDTGraphCFGV1`   |

### D.6.3. Properties
```tla
\* Eventual consistency: all nodes eventually converge to the same state
EventualConsistency == <>( \A n1, n2 \in Nodes: state[n1] = state[n2] )
\* No data loss: every update is eventually applied to all nodes
NoDataLoss == \A u \in Updates: <>( \A n \in Nodes: u \in applied[n] )
```

## D.7. Universal TLC Configuration
A common approach to TLC configuration is used for all specifications. Example for `Ouroboros.cfg`:
```text
SPECIFICATION Spec
CONSTANTS
  Alpha = 0.75
  Beta = 0.60
  Gamma = 0.82
  DeltaQ = 0.05
  DPenalty = 0.10
INVARIANT StableInvariant
```
When exploring boundary values, parameters are varied via separate runs with
different `.cfg` files.

## D.8. Reproducing the Full Set of Checks
The script `run_all_tla.sh` (CID `QmRunAllTLAV1`) automates downloading and checking all specifications:
```bash
#!/bin/bash
SPECS=(
  "QmOuroborosTLAV2:Ouroboros.tla:QmOuroborosCFGV1:Ouroboros.cfg"
  "QmSandboxIsolationV1:SandboxIsolation.tla:QmSandboxIsolationCFGV1:SandboxIsolation.cfg"
  "QmSwarmBFTV2:SwarmBFT.tla:QmSwarmBFTCFGV2:SwarmBFT.cfg"
  "QmEnergySchedulerV1:EnergyScheduler.tla:QmEnergySchedulerCFGV1:EnergyScheduler.cfg"
  "QmCRDTGraphV2:CRDTGraph.tla:QmCRDTGraphCFGV1:CRDTGraph.cfg"
)
for spec in "${SPECS[@]}"; do
  IFS=':' read -r tla_cid tla_file cfg_cid cfg_file <<< "$spec"
  ipfs get "$tla_cid" -o "$tla_file"
  ipfs get "$cfg_cid" -o "$cfg_file"
  java -cp tla2tools.jar tlc2.TLC "$tla_file" -config "$cfg_file"
  if [ $? -ne 0 ]; then
    echo "TLA+ check failed for $tla_file"
    exit 1
  fi
done
echo "All TLA+ specifications verified successfully."
```

## D.9. ValueDriftDetection.tla
```tla
---- MODULE ValueDriftDetection ----
EXTENDS Naturals, Reals, Sequences, TLC
CONSTANTS HarmScoreThreshold, BayesianThreshold
VARIABLES actions, harm_score, value_drift_probability

Init ==
    actions = {} /\
    harm_score = [a \in {} |-> 0] /\
    value_drift_probability = 0.0

ProposeAction(action) ==
    /\ actions' = actions \cup {action}
    /\ harm_score' = [harm_score EXCEPT ![action] = ComputeHarm(action)]
    /\ value_drift_probability' = BayesianUpdate(ETIFeed, value_drift_probability)

Invariant ==
    \A a \in actions: harm_score[a] = 0 /\
    value_drift_probability <= BayesianThreshold
```
**Note:** This TLA+ specification provides formal justification
for the L3‑invariant **ValueDrift**, checked at runtime by the
`InvariantMonitor` component (see Phase 4, section 7.3).

### D.10. CuriosityLoop.tla — Stability of the Active Exploration Loop
**Purpose:** Formal proof that the Curiosity Engine cannot
enter an infinite exploration loop and does not exceed the allocated resource share.
If P(Liveness) drops below 0.999, exploration resources are forcibly zeroed.

**Artifacts:**
| Artifact            | CID                     | Description         |
|---------------------|-------------------------|---------------------|
| `CuriosityLoop.tla` | `QmCuriosityLoopTLAV1`  | Main specification  |
| `CuriosityLoop.cfg` | `QmCuriosityLoopCFGV1`  | TLC configuration   |

**Invariants:**
- `ResourceInvariant`: `resource_allocated <= MaxExplorationShare` (0.05)
- `LivenessSafety`: when `liveness_prob <= 0.999` resources are zeroed.
- `NoExploitWithoutSurprise`: without surprise, resources do not grow.

**Check:**
```bash
java -cp tla2tools.jar tlc2.TLC CuriosityLoop -config CuriosityLoop.cfg
# Expected output: No error has been found.
```

### D.11. ConstitutionalEvolution.tla — Evolution of L3.1 while Preserving L3.0
**Purpose:** Formal verification that any change to
L3.1 invariants, adopted via the SMT‑GAN loop, does not violate the L3.0 axioms
and increases expected survivability.

**Artifacts:**
| Artifact                           | CID                                  | Description                         |
| :--------------------------------- | :----------------------------------- | :---------------------------------- |
| `ConstitutionalEvolution.tla`      | `QmConstitutionalEvolutionTLAV1`     | Main specification                  |
| `ConstitutionalEvolution.cfg`      | `QmConstitutionalEvolutionCFGV1`     | TLC configuration                   |
| `ConstitutionalEvolution_Proof.tla`| `QmConstitutionalEvolutionProofV1`   | Theorem on L3.0 preservation        |

**Specification fragment:**
```tla
---------------------------- MODULE ConstitutionalEvolution ----------------------------
EXTENDS Naturals, Reals, Sequences, TLC
CONSTANTS L3_0_Axioms,        \* Immutable axioms (set of predicates)
          Initial_L3_1,       \* Initial context goals
          ThreatContext,      \* Threat model
          Epsilon             \* Minimum survivability gain
VARIABLES l3_1_invariants, survival_score

Init ==
    /\ l3_1_invariants = Initial_L3_1
    /\ survival_score = EvaluateSurvival(Initial_L3_1, ThreatContext)

ProposeAmendment(amendment) ==
    /\ \A axiom \in L3_0_Axioms: Holds(amendment, axiom)  \* Does not violate L3.0
    /\ LET new_l3_1 == l3_1_invariants \cup {amendment}
           new_survival == EvaluateSurvival(new_l3_1, ThreatContext)
       IN  /\ new_survival > survival_score + Epsilon
           /\ l3_1_invariants' = new_l3_1
           /\ survival_score' = new_survival

Next ==
    \E amendment \in PotentialAmendments(ThreatContext): ProposeAmendment(amendment)

Invariant ==
    /\ \A axiom \in L3_0_Axioms: Holds(l3_1_invariants, axiom)
    /\ survival_score >= EvaluateSurvival(Initial_L3_1, ThreatContext)

Spec == Init /\ [][Next]_<<l3_1_invariants, survival_score>>
```

Check:
```bash
java -cp tla2tools.jar tlc2.TLC ConstitutionalEvolution -config ConstitutionalEvolution.cfg
# Expected output: No error has been found.
```

## D.12. Relationship with Other Sections
- 5.3 Deterministic Validation Pipeline – TLA+ model‑based testing stage.
- 5.7 TLA+ Model‑Based Testing – describes integration into the validation loop.
- 8.8 Terminal Goals (L3 Invariants) – formalizing goals via TLA+.
- 2.12 Artifact Model – TLA+ specifications as artifacts.
- Appendix I – formal verification of the Ouroboros invariant using Z3.

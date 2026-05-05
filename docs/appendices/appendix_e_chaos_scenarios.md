# Appendix E – Chaos Scenario Definitions

## E.1. General Principle
Chaos testing scenarios (sections 5.10–5.11) are no longer a static list in the document.
They are stored in machine‑readable format (YAML/JSON) as a signed artifact in IPFS. Each scenario
has a weight for computing the `ResilienceScore` (section 5.10.2) and is linked to specific modules or
phases. This appendix contains:
- a reference to the current scenarios artifact (CID);
- description of the structure and examples;
- table of scenarios with their parameters and weights;
- instructions for adding new scenarios and validation.

## E.2. Current Scenarios Artifact
| Field              | Value                                                                          |
| :----------------- | :----------------------------------------------------------------------------- |
| **CID (IPFS)**     | `QmChaosScenariosV3`                                                           |
| **BLAKE3 hash**    | `d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0`               |
| **File name**      | `chaos_scenarios.yaml`                                                         |
| **Schema version** | 2.0                                                                            |
| **Signature**      | `ed25519:4b3c5d6e…`                                                           |

**Download and verification:**
```bash
ipfs get QmChaosScenariosV3 -o chaos_scenarios.yaml
sha256sum chaos_scenarios.yaml
# Expected output: d1e2f3a4b5c6… chaos_scenarios.yaml
```

## E.3. Scenario File Structure
The file `chaos_scenarios.yaml` has the following structure:
```yaml
version: "2.0"
description: "Chaos engineering scenarios for Black Swan Phase 1-3"
last_updated: "2026-04-20T12:00:00Z"
default_resilience_weight: 0.1
scenarios:
  - id: "network_delay"
    type: "network"
    description: "Introduce fixed delay and jitter"
    params:
      delay_ms: 500
      jitter_ms: 100
    resilience_weight: 0.15
    applicable_phases: [1, 2, 3]
    expected_behavior: "degraded_performance"
    severity: "medium"
  - id: "packet_loss"
    type: "network"
    description: "Emulate packet loss"
    params:
      loss_percent: 10
    resilience_weight: 0.15
    applicable_phases: [1, 2, 3]
    expected_behavior: "retry_with_backoff"
    severity: "medium"
```

## E.4. Scenario Table
The following is a summary of all scenarios included in the current artifact `QmChaosScenariosV3`.

| ID                   | Type        | Parameters                                      | Weight | Phases | Severity |
| :------------------- | :---------- | :---------------------------------------------- | :----- | :----- | :------- |
| `network_delay`      | network     | delay_ms=500, jitter_ms=100                     | 0.15   | 1–3    | medium   |
| `packet_loss`        | network     | loss_percent=10                                 | 0.15   | 1–3    | medium   |
| `cpu_throttle`       | compute     | cpu_quota=0.5                                   | 0.15   | 1–3    | medium   |
| `memory_pressure`    | memory      | memory_limit_mb=512                             | 0.15   | 1–3    | medium   |
| `random_kill`        | fault       | probability=0.2                                 | 0.20   | 2–3    | high     |
| `byzantine_behavior` | byzantine   | corruption_probability=0.1                      | 0.25   | 3      | high     |
| `slow_loris`         | dos         | connections=50, keepalive_interval=10           | 0.10   | 2–3    | medium   |
| `clock_skew`         | time        | offset_seconds=3600                             | 0.10   | 2–3    | low      |
| `escape_attempt`     | security    | target_process=systemd, payload=harmless        | 0.30   | 0–3    | critical |

### E.4.1. Notes on Scenarios
- `escape_attempt` – emulates a fileless injection attempt. Weight 0.30 reflects the critical importance of isolation. If this scenario fails, the entire patch is rejected regardless of other metrics.
- `byzantine_behavior` – relevant only for Phase 3 (distributed swarm). Emulates compromise of an edge node.
- `random_kill` – applied only in the shadow environment; in production it is replaced with a controlled shutdown.

## E.5. Resilience Score Computation
The final `ResilienceScore` (section 5.10.2) is computed as the weighted geometric mean of the
results of individual scenarios:

```
ResilienceScore = (Π_{s in scenarios} score_s^{w_s})^{1 / Σ w_s}
```

Where:
- `score_s` – result of scenario `s` (0..1),
- `w_s` – `resilience_weight` from the scenario configuration.

Scenarios with `severity: critical` (`escape_attempt`) zero out the overall `ResilienceScore` if `score_s = 0`.

## E.6. Adding New Scenarios
1. Create a YAML description of the new scenario according to the schema (JSON Schema available at CID `QmChaosScenarioSchemaV1`).
2. Test the scenario locally in an isolated shadow environment.
3. Add the scenario to `chaos_scenarios.yaml`.
4. Sign and publish the new version:
   ```bash
   sign_artifact chaos_scenarios.yaml --key /etc/swarm/keys/node_key.pem
   ipfs add chaos_scenarios.yaml
   ```
5. Update the CID in `GlobalState.security_state.chaos_scenarios_cid`.

## E.7. Integration with the Validation Pipeline
Scenarios are loaded by `ShadowBenchmark` (Appendix C) when launching shadow testing:
```python
def load_chaos_scenarios():
    cid = GlobalState.security_state.chaos_scenarios_cid
    scenarios_yaml = ipfs.cat(cid)
    return yaml.safe_load(scenarios_yaml)['scenarios']
```
The results of each scenario are stored in the `ShadowBenchmarkArtifact` and influence
the decision on patch deployment.

## E.8. Relationship with Other Sections
- 5.10 Chaos Engineering in Shadow Environment – logic of fault injection.
- 5.10.2 Quantitative Resilience Scoring – ResilienceScore formula.
- 5.11 Extended Chaos Scenarios for Distributed Components – additional scenarios for the swarm.
- 9.2 Safety & Isolation Boundaries – `escape_attempt` as an isolation check.

## E.9. Change History
| Artifact version | Date       | Changes                                                    | CID                   |
| :--------------- | :--------- | :--------------------------------------------------------- | :-------------------- |
| V1               | 2026-01-15 | Basic scenarios (network, cpu, memory)                     | `QmChaosScenariosV1`  |
| V2               | 2026-03-10 | Added byzantine, slow_loris, clock_skew                    | `QmChaosScenariosV2`  |
| V3 (current)     | 2026-04-20 | Introduced resilience weights, added escape_attempt        | `QmChaosScenariosV3`  |

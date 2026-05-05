# Appendix C – Validation Code Listings

## C.1. General Principle
The code of validation modules (deterministic checking, property‑based tests, integration with Hypothesis
and TLA+) is no longer duplicated in the document. Instead, each significant piece of code is stored as
a separate signed artifact in IPFS. This appendix contains:
- a list of artifacts with their CIDs and checksums,
- a brief description of each module’s purpose,
- commands for download and verification,
- examples of key data structures to understand the logic.
All artifacts are part of the `core-tools` repository (Appendix K) and are accessible via the corresponding
CIDs.

## C.2. Deterministic Validation (Validation Pipeline)
### C.2.1. Main Module
**Purpose:** sequential execution of Ruff, mypy, pytest+Hypothesis, Bandit inside a sandbox with
early exit on first error. Returns a structured report in the artifact format
(section 2.12).

| Field              | Value                                                                          |
| :----------------- | :----------------------------------------------------------------------------- |
| **CID (IPFS)**     | `QmValidationPipelineV2`                                                       |
| **BLAKE3 hash**    | `f7e6d5c4b3a291807f6e5d4c3b2a1908f7e6d5c4b3a291807f6e5d4c3b2a1908`            |
| **File name**      | `deterministic_pipeline.py`                                                    |
| **Version**        | 2.0.1 (compatible with Python 3.12+)                                          |
| **Signature**      | `ed25519:8f7e6d…`                                                             |

**Download and verification:**
```bash
ipfs get QmValidationPipelineV2 -o deterministic_pipeline.py
sha256sum deterministic_pipeline.py
# Expected output: f7e6d5c4b3a2…  deterministic_pipeline.py
```

### C.2.2. Main Function Signature
```python
def run_deterministic_validation(
    generated_code: str,
    module_name: str = "temp_agent",
    sandbox_id: Optional[str] = None
) -> Tuple[bool, ValidationArtifact]:
    """
    Performs a full deterministic validation cycle.
    Returns (passed, artifact), where artifact contains:
    - stage_results: results of each stage (ruff, mypy, pytest, bandit)
    - metrics: execution time, number of errors
    - content_cid: CID of the saved report
    """
```

### C.2.3. ValidationArtifact Structure
```json
{
  "artifact_id": "art_val_20260420T120000Z",
  "type": "validation_report",
  "input_code_cid": "QmCode…",
  "stages": {
    "ruff": {"status": "passed", "issues": 0, "execution_time_ms": 120},
    "mypy": {"status": "passed", "type_errors": 0, "coverage": 0.92},
    "pytest": {"status": "passed", "tests_run": 42, "failures": 0},
    "bandit": {"status": "passed", "severity_high": 0, "severity_medium": 1}
  },
  "overall_status": "passed",
  "timestamp": "2026-04-20T12:00:00Z",
  "signature": "ed25519:…"
}
```

## C.3. Property‑Based Testing (Hypothesis)
### C.3.1. Base Test Module
**Purpose:** templates of Hypothesis strategies and decorators for checking properties of generated
code. Used inside the sandbox to discover edge cases.

| Field           | Value                     |
| :-------------- | :------------------------ |
| **CID (IPFS)**  | `QmHypothesisTestSuiteV1` |
| **BLAKE3 hash** | `a1b2c3d4e5f6…`           |
| **File name**   | `property_tests.py`       |

### C.3.2. Example Strategy
```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sum_even(lst):
    result = sum_even(lst)
    expected = sum(x for x in lst if x % 2 == 0)
    assert result == expected
```

The full set of strategies includes generators for:
- lists, dictionaries, recursive structures,
- floating‑point numbers (with nan/inf control),
- strings in various encodings.

## C.4. Integration with TLA+ Model Checker
### C.4.1. TLC Launch Script
**Purpose:** automatic generation of a TLC configuration file, running the model checker
inside a sandbox, and parsing the results.

| Field           | Value              |
| :-------------- | :----------------- |
| **CID (IPFS)**  | `QmTLAValidatorV1` |
| **BLAKE3 hash** | `c9d8e7f6a5b4…`    |
| **File name**   | `tla_validator.py` |

### C.4.2. Example of a Generated TLA+ Specification (fragment)
```text
---- MODULE SimpleAgentModule ----
EXTENDS Integers, TLC
VARIABLES state, memoryUsage

Init == state = "IDLE" /\ memoryUsage = 0

Next ==
  \/ state = "IDLE" /\ state' = "PROCESSING" /\ memoryUsage' = memoryUsage + 128
  \/ state = "PROCESSING" /\ state' = "IDLE" /\ memoryUsage' = 0

Invariant == memoryUsage <= 4096

Spec == Init /\ [][Next]_<<state, memoryUsage>>
```

Full specifications for various modules are available in Appendix D.

## C.5. Time‑Based Invariant Analysis (Time‑Based Invariants)
### C.5.1. Checking Module
**Purpose:** verification of code containing `# @time_invariant:` annotations using
freezegun or time‑machine.

| Field           | Value                         |
| :-------------- | :---------------------------- |
| **CID (IPFS)**  | `QmTimeInvariantCheckerV1`    |
| **BLAKE3 hash** | `d4c3b2a1908f7e…`             |
| **File name**   | `time_invariant_checker.py`   |

### C.5.2. Example Annotation and Check
```python
# @time_invariant: max_retry_delay < 5000
def retry_with_backoff():
    for attempt in range(3):
        try:
            return call_external()
        except Exception:
            time.sleep(1000 * (2 ** attempt))  # delay in ms
```
The module extracts annotations, emulates the passage of time, and checks the condition.

## C.6. Static Security Analysis (Bandit + Semgrep)
### C.6.1. Configuration and Wrapper
**Purpose:** unified execution of Bandit and Semgrep with custom rules, including prohibition of
`eval`, `exec`, `os.system`, and unsafe deserializations.

| Field           | Value                  |
| :-------------- | :--------------------- |
| **CID (IPFS)**  | `QmSecurityScannerV1`  |
| **BLAKE3 hash** | `e5f4a3b2c1d0…`        |
| **File name**   | `security_scanner.py`  |
| Semgrep rules   | `QmSemgrepRulesV1` (separate artifact) |

### C.6.2. Example Custom Semgrep Rule (YAML)
```yaml
rules:
  - id: no-eval
    pattern: eval(...)
    message: "eval() is forbidden in agent-generated code"
    severity: ERROR
  - id: no-subprocess-shell
    pattern: subprocess.run(..., shell=True)
    message: "shell=True is a security risk"
    severity: ERROR
```

## C.7. Shadow Benchmarking with Chaos Injections
### C.7.1. Shadow Testing Manager
**Purpose:** running code in an isolated shadow container, collecting performance metrics,
applying chaos scenarios, and comparing against a baseline using statistical methods (P1‑2).

| Field           | Value                  |
| :-------------- | :--------------------- |
| **CID (IPFS)**  | `QmShadowBenchmarkV2`  |
| **BLAKE3 hash** | `b8a7c6d5e4f3…`        |
| **File name**   | `shadow_benchmark.py`  |

### C.7.2. Main Functions
```python
def run_shadow_benchmark(
    new_code: str,
    baseline_metrics: dict,
    target_module: str,
    chaos_profile: Optional[str] = None
) -> ShadowBenchmarkArtifact:
    """
    Returns an artifact with metrics, regressions, and chaos test results.
    """
```
The result structure includes:
- throughput (p50, p95, p99),
- latency (p50, p95, p99),
- memory_peak_mb,
- resilience_score (P1‑6),
- regression_flags (if degradation exceeds a threshold).

## C.8. Chaos Engineering Scenarios (Executable)
### C.8.1. Fault Injection Scripts
**Purpose:** a set of executable scripts (in Python and Rust) that run inside the shadow container to emulate network delays, packet loss, CPU throttling, and escape attempts.

| Artifact         | CID                  | Description                                       |
| :--------------- | :------------------- | :------------------------------------------------ |
| `network_delay.py` | `QmChaosNetDelayV1`  | Introduces delay and jitter on a network interface|
| `packet_loss.py`   | `QmChaosPacketLossV1`| Emulates packet loss via tc‑netem                |
| `cpu_throttle.py`  | `QmChaosCpuV1`       | Limits CPU via cgroups                           |
| `escape_memfd.c`   | `QmEscapeMemfdV1`    | Fileless injection attempt (testing only)        |

All scripts are signed and run with restricted privileges.

## C.9. Artifact Integrity Verification
A manifest `validation_manifest.json`, available at CID `QmValidationManifestV2`, contains the list of all CIDs and their BLAKE3 hashes for verification.

Verification command:
```bash
ipfs get QmValidationManifestV2
jq -r '.artifacts[] | "\(.cid) \(.blake3)"' validation_manifest.json | while read cid hash; do
  ipfs get $cid -o tmp_file
  echo "$hash tmp_file" | sha256sum -c
done
```

## C.10. Relationship with Other Sections
- 5.3 Deterministic Validation Pipeline – logic and stage descriptions.
- 5.5 Unit and Property‑Based Testing – use of Hypothesis.
- 5.9–5.11 Shadow Benchmarking & Chaos – full testing cycle.
- 2.12 Artifact Model and Traceability – artifact structure.
- Appendix D – TLA+ specifications.

## C.11. Change History
| Version | Date       | Changes                                                                    | Manifest CID              |
| :------ | :--------- | :------------------------------------------------------------------------- | :------------------------ |
| V1      | 2026-01-15 | Initial set of scripts                                                    | `QmValidationManifestV1`  |
| V2      | 2026-04-20 | Added statistical metrics, resilience score, updated pipeline              | `QmValidationManifestV2`  |

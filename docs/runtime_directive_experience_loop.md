# Runtime Directive Experience Loop

BlackSwan now supports a controlled runtime experience loop:

```text
Directive
  -> DirectiveResult
  -> EvidenceRecord
  -> MemoryRecord
```

This loop turns a safe runtime action into verified evidence and then into memory that can be ingested, reviewed, exported, replayed, or used by future swarm intelligence.

The first validated directive is:

```text
REDUCE_RISK
```

It targets the trade swarm and safely forces:

```text
dry_run=True
execution_enabled=False
```

It never enables live execution.

---

## Purpose

This flow gives LLM agents and swarm coordinators a clean operational memory path.

Instead of reasoning from noisy logs, the system can record:

1. what instruction was issued,
2. which node applied it,
3. whether the application was verified,
4. what memory should be kept from the event.

This is the foundation for LLM-friendly runtime learning.

---

## Runtime chain

```text
manual or Overseer seed
  -> swarm_directive in CRDT
  -> trade command loop refreshes CRDT
  -> trade applies safe directive
  -> swarm_directive_result in CRDT
  -> evidence_record from directive lifecycle
  -> memory_record from evidence
```

---

## Start a local runtime

From the project root:

```bash
rm -f data/cluster_runtime/latest/ledgers/swarm_crdt.local.db*
rm -f data/cluster_runtime/latest/ledgers/events.local.db*

python -m src.swarms.runtime.cluster_cli up --duration 0 --no-strict
```

Keep this terminal running.

---

## Seed a safe directive

In another terminal:

```bash
python -m src.testing.seed_directive \
  --action REDUCE_RISK \
  --target trade \
  --target-type swarm \
  --source overseer-seed \
  --directive-id runtime-reduce-risk-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected seed log:

```text
Seeded directive: id=runtime-reduce-risk-1 action=REDUCE_RISK target=swarm:trade
```

---

## Verify directive result

Check logs:

```bash
grep -R "runtime-reduce-risk-1\|Published directive result\|directive_applied\|REDUCE_RISK\|command loop failed\|service exited: trade-1" \
  data/cluster_runtime/latest/logs \
  | tail -240
```

Expected trade log:

```text
Published directive result: directive_id=runtime-reduce-risk-1 status=applied
```

Check CRDT:

```bash
python - <<'PY'
from src.core.crdt_adapter import CRDTAdapter

path = "data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
crdt = CRDTAdapter(node_id="debug-reader", db_path=path)
state = getattr(crdt, "state", {}) or {}

for item in state.values():
    if isinstance(item, dict) and item.get("type") in {
        "swarm_directive",
        "swarm_directive_result",
    }:
        print(
            item.get("type"),
            item.get("directive_id"),
            item.get("action"),
            item.get("status"),
            item.get("source"),
            item.get("swarm"),
        )
PY
```

Expected output:

```text
swarm_directive runtime-reduce-risk-1 REDUCE_RISK issued overseer-seed None
swarm_directive_result runtime-reduce-risk-1 None applied trade-1 trade
```

---

## Publish evidence

After the directive result exists:

```bash
python -m src.testing.publish_directive_evidence \
  --directive-id runtime-reduce-risk-1 \
  --source manual-runtime-check \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected logs:

```text
Published directive evidence: subject=runtime_directive_seed_check status=passed confidence=1.0
Evidence check: name=directive_seeded status=passed value=True
Evidence check: name=directive_result_published status=passed value=True
Evidence check: name=directive_applied status=passed value=applied
```

---

## Bridge evidence into memory

After the evidence record exists:

```bash
python -m src.testing.evidence_memory_bridge \
  --directive-id runtime-reduce-risk-1 \
  --source evidence-memory-bridge \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected log:

```text
Published evidence memory record: subject=runtime_directive_seed_check status=passed directive_id=runtime-reduce-risk-1
```

---

## Inspect the full chain

```bash
python - <<'PY'
from src.core.crdt_adapter import CRDTAdapter

path = "data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"
crdt = CRDTAdapter(node_id="debug-reader", db_path=path)
state = getattr(crdt, "state", {}) or {}

for item in state.values():
    if isinstance(item, dict) and item.get("type") in {
        "swarm_directive",
        "swarm_directive_result",
        "evidence_record",
        "memory_record",
    }:
        print(
            item.get("type"),
            item.get("directive_id") or item.get("payload", {}).get("directive_id"),
            item.get("kind"),
            item.get("status"),
            item.get("source"),
            item.get("subject"),
        )
PY
```

Expected output:

```text
swarm_directive runtime-reduce-risk-1 None issued overseer-seed None
swarm_directive_result runtime-reduce-risk-1 None applied trade-1 None
evidence_record runtime-reduce-risk-1 None passed manual-runtime-check runtime_directive_seed_check
memory_record runtime-reduce-risk-1 runtime_evidence passed evidence-memory-bridge runtime_directive_seed_check
```

---

## Scenario regression

The end-to-end advisory loop is covered by:

```text
tests/unit/swarms/test_runtime_evidence_directive_scenario.py
```

This scenario validates:

```text
memory heartbeat runtime_evidence metrics
  -> Overseer memory intelligence
  -> global brief
  -> proposed directive
```
---

## Replay advisory extension

Verified runtime evidence can be converted into simulation replay scenarios.

```text
memory_record kind=runtime_evidence status=passed
  -> simulation_replay_scenario status=pending
  -> simulation heartbeat replay metrics
  -> Overseer global brief opportunity
  -> OBSERVE simulation proposed directive
```

The current replay loop is advisory-only. It does not execute replay scenarios automatically.

Replay scenarios are published with:

```bash
python -m src.testing.publish_replay_scenarios \
  --source simulation-replay-builder \
  --directive-id runtime-reduce-risk-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Simulation heartbeat reports:

- simulation_replay_scenarios
- simulation_replay_pending
- simulation_replay_completed
- simulation_replay_failed

Overseer global brief can then recommend:
```text
OBSERVE target=simulation
```
Actual replay execution remains a future gated step.

---

## Gated replay directive

`RUN_REPLAY` is recognized as a gated directive action.

Current behavior:

```text
swarm_directive action=RUN_REPLAY target=simulation
  -> security validation requires:
     - target=simulation
     - payload.scenario_id
     - payload.dry_run=true
  -> simulation consumes directive
  -> simulation publishes swarm_directive_result status=rejected
     reason=run_replay_execution_not_implemented
```

This intentionally does not execute replay scenarios yet.

Manual runtime check:

```bash
python -m src.testing.seed_directive \
  --action RUN_REPLAY \
  --target simulation \
  --target-type swarm \
  --source overseer-seed \
  --directive-id runtime-run-replay-json-1 \
  --payload-json '{"scenario_id":"replay-runtime-reduce-risk-1","dry_run":true}' \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected result:

```text
swarm_directive RUN_REPLAY issued overseer-seed
swarm_directive_result rejected simulation reason=run_replay_execution_not_implemented
```

RUN_REPLAY execution is reserved for a future dry-run replay executor.

---

## Replay execution evidence

Completed dry-run replay executions can be converted into evidence records:

```bash
python -m src.testing.publish_replay_execution_evidence \
  --scenario-id replay-runtime-reduce-risk-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

This publishes:
```text
simulation_replay_execution status=completed
  -> evidence_record subject=simulation_replay_execution_check status=passed
```

---

Replay execution evidence can be bridged into memory:

```bash
python -m src.testing.evidence_memory_bridge \
  --subject simulation_replay_execution_check \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

This produces:

```text
evidence_record subject=simulation_replay_execution_check status=passed
  -> memory_record kind=runtime_evidence subject=simulation_replay_execution_check
```
---

## Replay evidence memory lifecycle

The replay evidence lifecycle closes the dry-run replay loop:

```text
simulation_replay_scenario
  -> RUN_REPLAY directive
  -> simulation_replay_execution
  -> evidence_record subject=simulation_replay_execution_check
  -> memory_record kind=runtime_evidence
  -> MemorySummary replay_execution_evidence_* counters
  -> Memory swarm heartbeat memory_summary
  -> Overseer memory intelligence
  -> Global swarm brief
```

Manual runtime sequence:

```bash
python -m src.testing.seed_replay_scenario \
  --scenario-id replay-runtime-reduce-risk-1 \
  --action REDUCE_RISK \
  --expected-result-status applied \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db

python -m src.testing.seed_directive \
  --action RUN_REPLAY \
  --target simulation \
  --target-type swarm \
  --source overseer-seed \
  --directive-id runtime-run-replay-memory-1 \
  --payload-json '{"scenario_id":"replay-runtime-reduce-risk-1","dry_run":true}' \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db

python -m src.testing.publish_replay_execution_evidence \
  --scenario-id replay-runtime-reduce-risk-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db

python -m src.testing.evidence_memory_bridge \
  --subject simulation_replay_execution_check \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected CRDT trail:
```text
simulation_replay_execution completed
evidence_record simulation_replay_execution_check passed
memory_record runtime_evidence simulation_replay_execution_check passed
```
Expected summary/brief trail:
```text
MemorySummary.replay_execution_evidence_records >= 1
MemorySummary.replay_execution_evidence_passed >= 1
memory_intelligence.aggregate.replay_execution_evidence_records >= 1
global_brief.key_metrics.memory_replay_execution_evidence_records >= 1
```

---

## One-command replay evidence check

The full controlled replay evidence lifecycle can be exercised with:

```bash
python -m src.testing.run_replay_evidence_check \
  --scenario-id replay-runtime-reduce-risk-1 \
  --action REDUCE_RISK \
  --directive-id runtime-run-replay-e2e-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

The helper seeds the replay scenario, seeds the RUN_REPLAY directive, waits for
simulation_replay_execution, publishes replay evidence, bridges evidence into
memory, and reports explicit checks.

---
The helper also publishes replay_evidence_lifecycle_result with explicit checks.

Security validation now recognizes `replay_evidence_lifecycle_result` records.
A passed lifecycle result is valid only when all checks are passed.

The helper also verifies Overseer-ready visibility by checking MemorySummary replay evidence counters and Security validation record-type counts.

It also records `trail_counts` for the expected CRDT trail:
`simulation_replay_scenario`, `swarm_directive`, `simulation_replay_execution`,
`evidence_record`, `memory_record`, and `replay_evidence_lifecycle_result`.

The helper reports an explicit `visibility_crdt_trail_complete` check. It passes
when the CRDT trail contains all expected record types for the target scenario
and directive.

The command exits with code `0` when the lifecycle check passes and `1` when any check fails.

When execution is not observed before the configured wait timeout, the lifecycle
result payload includes `failure_reason=execution_not_observed_before_timeout`
plus `wait_seconds` and `poll_interval`.

Structured lifecycle failures are valid warnings and are aggregated in
`security_validation_warning_reasons`, for example
`execution_not_observed_before_timeout`.

Overseer global briefs surface structured Security warning reasons such as
`execution_not_observed_before_timeout` as replay lifecycle timeout warnings.

When replay lifecycle timeout warnings are observed, the global brief recommends
`retry_replay_lifecycle_check` with a longer wait window before investigating
simulation responsiveness.

The helper supports timeout profiles with `--timeout-profile`:

- `fast`: short smoke/failure timeout.
- `standard`: recommended retry profile for `retry_replay_lifecycle_check`.
- `patient`: longer wait for slow runtimes.

A retry recommendation can be executed with:

```bash
python -m src.testing.run_replay_evidence_check \
  --scenario-id replay-runtime-reduce-risk-1 \
  --action REDUCE_RISK \
  --directive-id runtime-run-replay-retry-1 \
  --timeout-profile standard \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

The retry recommendation uses `timeout_profile=standard`, which maps to
`wait_seconds=15.0` and `poll_interval=0.5`.

The retry recommendation also includes a `command_template` with placeholders for
`<scenario_id>` and `<new_directive_id>` so an operator or controlled agent can
construct a retry command safely.

---

## Replay lifecycle retry proposals

Replay lifecycle timeout recommendations can be converted into pending
`replay_lifecycle_retry_proposal` records. These proposals are safe by default:
they contain a retry command template and timeout profile, but they do not execute
the retry automatically.

Overseer can publish pending `replay_lifecycle_retry_proposal` records from retry
recommendations. These proposals remain non-executing until a future approval or
runner consumes them.

Security validation recognizes pending `replay_lifecycle_retry_proposal` records.
Only non-executing `pending` retry proposals with safe timeout profiles such as
`standard` or `patient` are valid.

Overseer global briefs surface validated pending `replay_lifecycle_retry_proposal`
records as retry proposal opportunities.

---

## Replay lifecycle retry approvals

Retry proposals are not executed directly. A separate
`replay_lifecycle_retry_approval` record can approve or reject a pending proposal.
Approvals are auditable and must keep `execution_enabled=false` until a future
runner/approval policy explicitly supports execution.

Overseer global briefs also surface validated `replay_lifecycle_retry_approval`
records as retry approval opportunities.

Retry approvals include `decision_mode=manual|policy`. Autonomous approval is not valid until a future policy/runner layer explicitly supports it.

Security heartbeat metrics include
`security_validation_retry_approval_decision_modes` so manual and policy retry
approvals can be observed separately.

Overseer global briefs surface retry approval decision modes through
`security_retry_approval_decision_modes`, including separate manual and policy
approval counts.

---

## Safety guarantees

The current controlled loop is intentionally conservative:

* only safe seed actions are allowed,
* `REDUCE_RISK` and `SET_DRY_RUN` cannot enable execution,
* trade directive consumer rejects unsafe actions such as enabling live execution,
* evidence is generated from CRDT-observed records,
* memory records are explicit `runtime_evidence` records,
* no autonomous escalation is performed by this helper chain.

---

## Related modules

```text
src/swarms/common/protocols/briefs.py
src/swarms/common/protocols/directives.py
src/swarms/common/protocols/evidence.py

src/testing/seed_directive.py
src/testing/directive_evidence.py
src/testing/publish_directive_evidence.py
src/testing/evidence_memory_bridge.py

src/swarms/trade/node_core/directive_consumer.py
src/swarms/trade/node_core/crdt_refresh.py
```

---

RUN_REPLAY currently executes a dry-run replay skeleton:
- loads simulation_replay_scenario by scenario_id
- validates dry_run=True
- returns simulation_replay_execution receipt
- no live/external side effects

---

```bash
rm -f data/cluster_runtime/latest/ledgers/swarm_crdt.local.db*
rm -f data/cluster_runtime/latest/ledgers/events.local.db*

python -m src.swarms.runtime.cluster_cli up \
  --duration 0 \
  --no-strict \
  --simulation-nodes 1 \
  --simulation-heartbeat-interval 5
```

CLI:

```bash
python -m src.testing.seed_replay_scenario \
  --scenario-id replay-runtime-reduce-risk-1 \
  --action REDUCE_RISK \
  --expected-result-status applied \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db

python -m src.testing.seed_directive \
  --action RUN_REPLAY \
  --target simulation \
  --target-type swarm \
  --source overseer-seed \
  --directive-id runtime-run-replay-cli-live-1 \
  --payload-json '{"scenario_id":"replay-runtime-reduce-risk-1","dry_run":true}' \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
```bash
grep -R "runtime-run-replay-cli-live-1\|run_replay_dry_run_completed" \
  data/cluster_runtime/latest/logs \
  | tail -120
```
```bash
tail -200 data/cluster_runtime/latest/logs/simulation-1.log
```
```bash
python -m src.testing.run_replay_evidence_check \
  --scenario-id replay-runtime-reduce-risk-timeout-2 \
  --action REDUCE_RISK \
  --directive-id runtime-run-replay-timeout-2 \
  --wait-seconds 0.01 \
  --poll-interval 0.01 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db

echo $?
```
---

## Next steps

Planned follow-up work:

1. Memory swarm consumes `runtime_evidence` memory records.
2. Overseer links evidence records back into briefs.
3. Security validates directives and directive results.
4. Dashboard shows briefs, directives, results, evidence, and memory records.
5. Simulation can replay verified runtime evidence as scenarios.

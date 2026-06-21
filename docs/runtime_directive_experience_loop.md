# Runtime Directive Experience Loop

BlackSwan now supports a controlled runtime experience loop:

```text
Directive
  -> DirectiveResult
  -> EvidenceRecord
  -> MemoryRecord
```

This loop turns a safe runtime action into verified evidence and then into memory that can be ingested, reviewed, exported, replayed, or used by future swarm intelligence.

The same audit-first pattern now extends into controlled retry governance,
guarded read-only execution, repair planning, guarded repair execution, and
post-repair verification:

```text
RetryGovernance
  -> ControlledExecution
  -> RealExecutionPreflight
  -> DryRunEnvelope
  -> NoopHarness
  -> GuardedReadOnlyExecution
  -> ReadOnlyFeedback
  -> RepairPlan
  -> RepairActionBundleReview
  -> RepairApproval
  -> RepairDryRunEnvelope
  -> RepairNoopHarness
  -> RepairReadinessGate
  -> GuardedRepairExecution
  -> PostRepairEvidence
  -> close_repair_loop
```

The current verified milestone is the guarded repair loop. It proves that a
failed read-only evidence path can produce actionable feedback, a reviewed repair
plan, guarded repair execution, and a post-repair evidence check while keeping
arbitrary real execution disabled.

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

## Replay lifecycle retry execution plans

Approved retry proposals can be converted into non-executing `replay_lifecycle_retry_execution_plan` records with `status=planned` and `execution_enabled=false`, without executing the retry automatically.

Security validation recognizes `replay_lifecycle_retry_execution_plan` records.
Only non-executing plans with `status=planned`, `execution_enabled=false`, safe
timeout profiles, and manual or policy decision modes are valid.

Overseer global briefs surface validated `replay_lifecycle_retry_execution_plan`
records as retry execution plan opportunities.

---

## Replay retry plan runner

`src.testing.run_retry_execution_plans` is a dry-run runner for
`replay_lifecycle_retry_execution_plan` records. It does not execute command
templates. With `execution_enabled=false`, it publishes
`replay_lifecycle_retry_execution_result` with `status=skipped` and
`reason=execution_disabled`. If execution is enabled before runner support, it
publishes `status=rejected` with `reason=execution_not_supported`.


Security validation recognizes `replay_lifecycle_retry_execution_result` records.
Dry-run runner results are valid only when they are non-executing, such as
`status=skipped`, `reason=execution_disabled`, and `executed=false`.

Overseer global briefs surface validated `replay_lifecycle_retry_execution_result`
records as retry execution result opportunities.

Security heartbeat metrics include
`security_validation_retry_execution_result_statuses` and
`security_validation_retry_execution_result_reasons` for dry-run retry runner
results.

Overseer global briefs surface retry execution result status and reason
breakdowns through `security_retry_execution_result_statuses` and
`security_retry_execution_result_reasons`.
---

## Retry governance trail inspection

`src.testing.inspect_retry_governance_trail` is a read-only helper for inspecting
the end-to-end retry governance trail. It reports proposal, approval, execution
plan, and execution result counts, including skipped and rejected dry-run runner
results. The helper does not publish records and does not execute retry commands.

The retry governance trail summary includes `chain_complete` and `missing_stages`
so CI and operators can detect incomplete proposal-to-result chains.

The inspection helper supports `--require-complete`, which exits with code `1`
when `chain_complete=false` and code `0` when the proposal-to-result trail is
complete.

---

## Synthetic retry governance trail seeding

`src.testing.seed_retry_governance_trail` seeds a complete synthetic governance
trail for smoke tests: proposal, approval, execution plan, and skipped execution
result. It uses safe timeout profiles and non-executing records, so
`src.testing.inspect_retry_governance_trail --require-complete` can verify
`chain_complete=true` without running replay commands.

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

## Retry governance observability check

`src.testing.check_retry_governance_observability` is a read-only helper that
checks Security validation metrics and Overseer global brief key metrics for
retry governance visibility. It exits with code `0` when the proposal, approval,
execution plan, execution result, skipped status, and execution-disabled reason
are all visible; otherwise it exits with code `1`.

---

## One-command retry governance smoke

`src.testing.retry_governance_smoke` seeds a synthetic non-executing retry
governance trail, verifies `chain_complete=true`, and checks Security/Overseer
observability in one command.
The one-command retry governance smoke verifies Security/Overseer observability.

Runtime smoke checklist command:

```bash
python -m src.testing.retry_governance_smoke \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This command seeds a synthetic non-executing retry governance trail, verifies
chain_complete=true, and checks Security/Overseer observability.

---

`src.testing.swarm_runtime_smoke` includes the retry governance smoke on an
isolated temporary CRDT database, so the main runtime smoke gate verifies the
safe proposal-to-result governance path without polluting the live ledger.

The smoke command also supports `--require-clean`; when enabled, it exits with
code `1` before seeding if retry governance records already exist for the selected
proposal id. existing_retry_governance_records

---

## Replay retry rendered commands

`replay_lifecycle_retry_rendered_command` records are non-executing rendered
commands derived from retry execution plans. Rendering only replaces
`<scenario_id>` and `<new_directive_id>`, keeps `execution_enabled=false`, and
does not run shell commands.

Security validation recognizes `replay_lifecycle_retry_rendered_command` records.
Rendered retry commands are valid only when they are non-executing, call
`python -m src.testing.run_replay_evidence_check`, include scenario/directive ids,
use safe timeout profiles, and avoid shell operators.

Overseer global briefs surface validated `replay_lifecycle_retry_rendered_command`
records as retry rendered command opportunities.

Security heartbeat metrics include
`security_validation_retry_rendered_command_profiles` and
`security_validation_retry_rendered_command_decision_modes` for rendered retry
commands.

Overseer global briefs surface rendered retry command profile and decision-mode
breakdowns through `security_retry_rendered_command_profiles` and
`security_retry_rendered_command_decision_modes`.

Retry governance smoke includes the rendered command stage:
proposal, approval, execution plan, rendered command, and execution result.

---

## Rendered retry command dry-run runner

`src.testing.run_rendered_retry_commands` reads
`replay_lifecycle_retry_rendered_command` records and publishes
`replay_lifecycle_retry_rendered_command_result` records without executing the
command text. Disabled rendered commands are recorded as `status=skipped`,
`reason=execution_disabled`, and `executed=false`; enabled rendered commands are
recorded as `status=rejected`, `reason=execution_not_supported`, and
`executed=false`, without executing the command text.

Security validation recognizes `replay_lifecycle_retry_rendered_command_result`
records. Rendered command dry-run results are valid only when they remain
non-executing: skipped results use `reason=execution_disabled`, rejected enabled
commands use `reason=execution_not_supported`, and all valid records keep
`executed=false`.

Overseer global briefs surface
`replay_lifecycle_retry_rendered_command_result` records, including rendered
command dry-run result statuses and reasons such as `skipped`,
`execution_disabled`, `rejected`, and `execution_not_supported`. Rendered command dry-run results, replay_lifecycle_retry_rendered_command_result, rendered command dry-run result statuses.

`src.testing.retry_governance_smoke` also runs the rendered command dry-run
runner and requires `replay_lifecycle_retry_rendered_command_result` visibility
through Security metrics and Overseer brief key metrics. rendered command dry-run runner, replay_lifecycle_retry_rendered_command_result visibility.

The retry governance smoke now reports the full six-stage governance trail:
proposal, approval, execution plan, rendered command, rendered command result,
and execution result. Its summary includes `chain_records=6`,
`six_stage=true`, and `rendered_results=1` when the safe dry-run path is
complete.

---

## Retry execution eligibility gate

`src.testing.build_retry_execution_eligibility` publishes
`replay_lifecycle_retry_execution_eligibility` records for rendered retry
commands. The eligibility gate is non-executing: it keeps
`execution_supported=false`, publishes `status=blocked`, and records block
reasons such as `execution_disabled`, `execution_not_supported`,
`missing_rendered_command_result`, or `missing_rendered_command`.


Security validation recognizes `replay_lifecycle_retry_execution_eligibility`
records. Eligibility records are valid only when execution remains blocked:
`status=blocked`, `execution_supported=false`, `execution_enabled=false`, and
`executed=false`, with block reasons such as `execution_disabled`,
`execution_not_supported`, `missing_rendered_command_result`, or
`missing_rendered_command`.

Overseer global briefs surface `replay_lifecycle_retry_execution_eligibility`
records as retry execution eligibility observations. Brief summaries report
blocked eligibility status and block reasons such as `execution_disabled`,
`execution_not_supported`, `missing_rendered_command_result`, and
`missing_rendered_command`.

`src.testing.retry_governance_smoke` runs the retry execution eligibility gate
after the rendered command dry-run runner. The smoke requires at least one
`replay_lifecycle_retry_execution_eligibility` record with `status=blocked`,
so the safe governance path remains non-executing before any future controlled
runner.

The retry governance smoke now reports the full seven-stage safe governance
trail: proposal, approval, execution plan, rendered command, rendered command
result, execution eligibility, and execution result. Its summary includes
`chain_records=7`, `seven_stage=true`, `eligibilities=1`, and
`execution_blocked=1` when the safe path is complete. full seven-stage safe governance trail.

The retry execution eligibility builder is idempotent for a rendered command.
If an eligibility record already exists for the rendered command or plan, the
builder skips publishing a duplicate and leaves the existing blocked decision
in place.

The rendered retry command dry-run runner is idempotent for a rendered command.
If a `replay_lifecycle_retry_rendered_command_result` already exists for the
rendered command or plan, the runner skips publishing a duplicate and leaves the
existing skipped dry-run result in place.

The retry governance seed helper is idempotent for explicit governance ids.
If a proposal, approval, execution plan, rendered command, or execution result
already exists with the requested id, the seed helper skips publishing a
duplicate and leaves the existing governance record in place.

`src.testing.retry_governance_smoke` is idempotent when rerun without
`--require-clean`. If the safe seven-stage trail already exists and is complete,
the smoke can pass with `records_seeded=0`, `rendered_command_results=0`, and
`eligibility_results=0` while reporting `existing_complete=true`.

When `src.testing.retry_governance_smoke --require-clean` finds existing retry
governance records, it still fails the clean preflight, but it reports whether
the existing seven-stage trail is already complete. A complete existing trail is
reported with `existing_complete=true`, `existing_rendered_results=1`,
`existing_eligibilities=1`, and `existing_execution_blocked=1`.

---

## Seven-stage retry governance safe path

The retry governance safe path is a non-executing seven-stage control trail:

1. `replay_lifecycle_retry_proposal`
2. `replay_lifecycle_retry_approval`
3. `replay_lifecycle_retry_execution_plan`
4. `replay_lifecycle_retry_rendered_command`
5. `replay_lifecycle_retry_rendered_command_result`
6. `replay_lifecycle_retry_execution_eligibility`
7. `replay_lifecycle_retry_execution_result`

This path is intentionally safe: rendered retry commands are only dry-run
rendered, rendered command results are skipped when execution is disabled, and
execution eligibility remains blocked until a future controlled runner is
explicitly introduced.

### Canonical smoke command

```bash
python -m src.testing.retry_governance_smoke \
  --proposal-id replay-retry-seven-stage-smoke-1 \
  --approval-id replay-retry-seven-stage-approval-1 \
  --plan-id replay-retry-seven-stage-plan-1 \
  --rendered-command-id replay-retry-seven-stage-command-1 \
  --result-id replay-retry-seven-stage-result-1 \
  --require-clean \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
````

Expected output includes:

```text
status=passed
records_seeded=5
chain_records=7
seven_stage=true
rendered_command_results=1
eligibility_results=1
execution_blocked=1
chain_complete=true
observability=passed
```

### Inspector check

```bash
python -m src.testing.inspect_retry_governance_trail \
  --require-complete \
  --proposal-id replay-retry-seven-stage-smoke-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected output includes:

```text
chain_complete=true
missing_stages=none
```

The JSON form should include:

```json
{
  "counts": {
    "proposals": 1,
    "approvals": 1,
    "plans": 1,
    "rendered_commands": 1,
    "rendered_command_results": 1,
    "eligibilities": 1,
    "results": 1
  },
  "eligibility_statuses": {
    "blocked": 1
  },
  "eligibility_reasons": {
    "execution_disabled": 1
  }
}
```

### Observability check

```bash
python -m src.testing.check_retry_governance_observability \
  --proposal-id replay-retry-seven-stage-smoke-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected output includes:

```text
status=passed
```

Security/Overseer brief metrics should include:

```text
security_retry_rendered_commands=1
security_retry_rendered_command_results=1
security_retry_execution_eligibilities=1
security_retry_execution_blocked=1
```

### Idempotent rerun behavior

Rerunning `src.testing.retry_governance_smoke` without `--require-clean` against
the same ids is expected to pass without publishing duplicates:

```text
status=passed
records_seeded=0
rendered_command_results=0
eligibility_results=0
existing_complete=true
chain_complete=true
observability=passed
```

Rerunning with `--require-clean` against existing ids is expected to fail the
clean preflight while still reporting the existing complete trail:

```text
status=failed
reason=existing_retry_governance_records
existing_complete=true
existing_rendered_results=1
existing_eligibilities=1
existing_execution_blocked=1
```

This failure is intentional: `--require-clean` means the operator requested a
fresh trail and existing records violate that precondition.

### Controlled execution boundary

The current seven-stage path does not execute rendered retry commands. It only
renders commands, records a skipped dry-run result, records blocked execution
eligibility, and records the safe skipped execution result. Any future controlled
runner must preserve this default non-executing behavior unless explicit policy
and operator controls enable a narrower execution mode.

---

- Retry governance seven-stage smoke:
  `python -m src.testing.retry_governance_smoke --require-clean ...`
  Expected: `chain_records=7`, `seven_stage=true`, `execution_blocked=1`.

---

### Pre-controlled-runner readiness

Before designing or enabling any controlled retry runner, operators can run a
read-only readiness check:

```bash
python -m src.testing.check_retry_controlled_runner_readiness \
  --proposal-id replay-retry-seven-stage-smoke-1 \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

The readiness check does not execute rendered commands. It verifies that the
seven-stage safe path is complete, observability passes, rendered command
results are skipped, execution eligibility remains blocked, execution results
are skipped, and Security reports no invalid or critical validation records.

Expected output for a complete safe baseline includes:

```text
status=passed
readiness_score=100
controlled_execution_enabled=false
recommendation=ready_for_controlled_runner_design
```

---

### Controlled retry runner contract

The controlled retry runner is not implemented yet. Before implementation, the
project defines the following contract for any future controlled execution path.

#### Default posture

Controlled retry execution is disabled by default. The safe seven-stage retry
governance path remains non-executing unless a future runner receives explicit
operator authorization and passes all readiness and validation gates.

A future controlled runner must never execute rendered retry commands merely
because a command was rendered, approved, or marked eligible. Rendering,
approval, and eligibility are necessary but not sufficient for execution.

#### Required gates

A future controlled retry runner must require all of the following before it can
attempt execution:

- `src.testing.check_retry_controlled_runner_readiness` reports
  `status=passed` and `readiness_score=100`.
- The seven-stage safe governance trail is complete.
- Security/Overseer observability reports the trail as passed.
- The rendered command has a prior
  `replay_lifecycle_retry_rendered_command_result` with `status=skipped`.
- The execution eligibility record exists and remains `status=blocked`.
- The approval, execution plan, and rendered command explicitly opt in with
  `execution_enabled=true`.
- The operator provides an explicit controlled-execution flag, such as
  `--allow-controlled-execution`.
- The command matches an allowlisted module invocation.

#### Initial allowlist

The initial controlled runner allowlist is limited to:

```text
python -m src.testing.run_replay_evidence_check
```

The runner must reject arbitrary shell commands, `shell=True`, chained commands,
unrecognized Python modules, and commands that request network, trading, or other
side effects outside the explicit allowlist.

#### Required rejection behavior

A future controlled runner must reject or skip execution when any of the
following is true:

* readiness is missing or not `readiness_score=100`;
* the safe seven-stage trail is incomplete;
* Security reports invalid or critical validation records;
* the rendered command result is missing;
* execution eligibility is missing;
* execution eligibility is not blocked before the controlled decision;
* approval, plan, or rendered command does not explicitly set
  `execution_enabled=true`;
* the operator flag is missing;
* the command is not allowlisted;
* a controlled execution result already exists for the rendered command.

#### Controlled execution result

A future controlled runner must publish a new record type rather than mutating
the safe baseline trail:

```text
replay_lifecycle_retry_controlled_execution_result
```

The result must include:

* `controlled_execution_result_id`
* `rendered_command_id`
* `plan_id`
* `proposal_id`
* `approval_id`
* `status`: `executed`, `skipped`, or `rejected`
* `reason`
* `execution_enabled`
* `operator_authorized`
* `allowlist_matched`
* `readiness_score`
* `payload.executed`

The controlled execution result must be idempotent for a rendered command. A
second run for the same rendered command must not publish a duplicate controlled
execution result.

#### Non-goals for the first implementation

The first controlled runner implementation must not support arbitrary command
execution, live trading, network side effects, shell pipelines, background
processes, or unrestricted subprocess execution.

The first implementation may start as a skeleton that always publishes
`status=rejected` or `status=skipped` while proving that the contract, validation,
idempotency, and observability surfaces are correct.

must not support arbitrary command execution.
---

This readiness score is a prerequisite for controlled runner design, not a
permission to execute commands. not a permission to execute commands.

---

### Reject-only controlled runner skeleton

The first implementation is a reject-only skeleton:

```bash
python -m src.testing.run_controlled_retry_command \
  --rendered-command-id <rendered-command-id> \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

This command publishes replay_lifecycle_retry_controlled_execution_result with
status=rejected, reason=controlled_execution_not_implemented,
operator_authorized=false, allowlist_matched=false, and
payload.executed=false. It is idempotent for a rendered command and does not
execute the rendered command.

---

Security validates `replay_lifecycle_retry_controlled_execution_result` records.
In the reject-only skeleton phase, Security accepts only rejected results with
`reason=controlled_execution_not_implemented`, `operator_authorized=false`,
`allowlist_matched=false`, and `payload.executed=false`.

The Overseer brief surfaces controlled execution result visibility from Security
metrics. In the reject-only phase it reports the controlled execution result
count, rejected/skipped/executed status counts, and
`controlled_execution_not_implemented` reason count.

The governance trail inspector treats
`replay_lifecycle_retry_controlled_execution_result` as an optional controlled
execution extension. It reports controlled execution result counts, statuses,
reasons, ids, and `extended_controlled_execution_observed=true`, but the safe
seven-stage `chain_complete=true` result does not require a controlled execution
result. optional controlled execution extension, does not require a controlled execution result.

The controlled runner now includes a read-only command allowlist parser. The
parser recognizes only `python -m src.testing.run_replay_evidence_check`,
extracts required arguments, rejects shell chaining/redirection and unknown
modules, and reports `execution_performed=false`. Parser allowlist matches do not
enable execution; the controlled runner remains reject-only with
`reason=controlled_execution_not_implemented`. Parser allowlist matches do not enable execution.

Controlled command parse observability is surfaced through Security metrics,
the governance trail inspector, controlled execution observability, and Overseer
briefs. A valid parser observation reports `command_parse_valid=1`,
`command_parse_allowlisted=1`, and `command_parse_execution_performed=0`.

The `--allow-controlled-execution` flag records explicit operator authorization
intent as `operator_authorized=true`, but PR 29.3 still does not execute
commands. Authorized intent remains valid only while
`status=rejected`, `reason=controlled_execution_not_implemented`, and
`payload.executed=false`.

Controlled execution gate observability surfaces the nested `gate_evaluation`
from controlled execution results. The gate reports `gate_status=blocked`,
`would_execute=false`, `execution_performed=false`, and reason counts such as
`controlled_execution_not_enabled` and
`controlled_execution_implementation_not_enabled`.

---

### Controlled mock execution adapter

The controlled mock execution adapter produces an execution-shaped envelope
without invoking subprocesses. It may report `mock_executed`, but real execution
remains disabled: `payload.executed=false` and `subprocess_invoked=false`.

---

### Controlled execution readiness report

Before introducing any execution adapter, the controlled execution readiness
helper aggregates the seven-stage retry governance trail, retry governance
observability, controlled execution observability, command parse observability,
operator authorization intent, and gate evaluation.

```bash
python -m src.testing.check_controlled_execution_readiness \
  --proposal-id <proposal-id> \
  --rendered-command-id <rendered-command-id> \
  --require-operator-authorized \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
Expected safe pre-execution output:

```text
status=passed
ready_for_mock_execution=true
ready_for_real_execution=false
blocking_reasons=real_execution_not_supported_yet
```

The report is read-only and does not execute commands. Real execution remains
unsupported until a separate execution adapter PR explicitly introduces it.

---

### Controlled execution observability check

The reject-only controlled execution extension has a dedicated read-only
observability check:

```bash
python -m src.testing.check_controlled_retry_execution_observability \
  --rendered-command-id <rendered-command-id> \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected output for the skeleton phase includes:
```text
status=passed
controlled_execution_observed=true
controlled_execution_results=1
rejected=1
executed=0
controlled_execution_not_implemented=1
controlled_execution_enabled=false
```
The check fails if the controlled execution result is missing, if
payload.executed=true, if operator_authorized=true, or if the Security
validation metrics do not observe the controlled execution result.

---

### Mock execution visibility

Mock execution is surfaced in the governance trail inspector, Overseer brief,
and final readiness report. A safe mock run reports `mock_executed=1`,
`mock_performed=1`, and `mock_subprocess_invoked=0`. Real execution remains
disabled. Real execution remains disabled.

---

### Mock execution summary records

Mock execution summary records are derived from controlled execution results and
are idempotent by `controlled_execution_result_id`. A safe summary reports
`mock_summary_executed=1`, `mock_summary_performed=1`, and
`mock_summary_subprocess_invoked=0`.

---

When `run_controlled_retry_command` is invoked with `--mock-execution`, it
publishes the controlled execution result and automatically derives the
`replay_lifecycle_retry_mock_execution_summary` record. Re-running the same
mock path remains idempotent and does not duplicate either record.

---

### Controlled retry execution adapter contract

The controlled retry execution adapter contract is defined before real execution
support. The only supported adapter is `mock`. Unsupported adapters such as
`real` or subprocess-backed adapters are rejected.

Required invariants:

- `payload.executed=false`
- `subprocess_invoked=false`
- `real_execution_enabled=false`

The mock adapter returns an execution-shaped result with
`adapter=mock`, `mode=mock`, `status=mock_executed`, and
`reason=mock_execution_completed`, but it never invokes subprocesses.

---

### Adapter contract observability

Adapter contract observability surfaces the nested adapter result from mock
execution envelopes. A safe adapter contract reports `adapter=mock`, `mode=mock`,
`mock_executed=1`, `subprocess_invoked=0`, `real_execution_enabled=0`, and
`payload_executed=0`.

---

### Adapter contract readiness gates

The final controlled execution readiness report requires the adapter contract to
be observed before mock execution is considered ready. The required safe adapter
gates are:

- `adapter_contract_observed=true`
- `adapter_mock=1`
- `adapter_mode_mock=1`
- `adapter_result_mock_executed=1`
- `adapter_subprocess_invoked=0`
- `adapter_real_execution_enabled=0`
- `adapter_payload_executed=0`

These gates keep mock execution separate from real execution and prevent any
subprocess-backed adapter from being treated as ready.

---

### Adapter contract violation fixtures

Adapter contract violation fixtures prove that the readiness report fails closed.
The controlled execution readiness gate fails if any adapter contract violation is
observed:

- `adapter_subprocess_invoked=true`
- `adapter_real_execution_enabled=true`
- `adapter_payload_executed=true`
- `adapter != mock`
- `mode != mock`

These negative fixtures ensure that mock readiness cannot be confused with real
execution readiness.

---

### Controlled execution readiness JSON schema

The controlled execution readiness report exposes a stable machine-readable
contract with `schema_version=controlled-execution-readiness/v1` and
`schema_kind=controlled_execution_readiness`.

Required top-level fields include `ready_for_mock_execution`,
`ready_for_real_execution`, `blocking_reasons`, `adapter_contract_observed`,
`adapter_subprocess_invoked`, `adapter_real_execution_enabled`,
`adapter_payload_executed`, `checks`, and `exit_codes`.

`ready_for_real_execution` must remain `false` until a separate real-adapter PR
explicitly changes the contract.

---

The JSON schema is covered by regression fixtures that snapshot the required
public fields and verify that `checks`, `exit_codes`, adapter contract counters,
and `ready_for_real_execution=false` remain present and machine-readable. required public fields.

---

### Real adapter placeholder

The real controlled retry execution adapter is explicitly represented as an
unsupported placeholder. The adapter contract reports
`real_execution_supported=false`, `subprocess_supported=false`,
`real_adapter_supported=false`, and `real_adapter_runnable=false`.

Requesting the `real` adapter fails closed and requires a separate explicit PR
before any real execution support can exist.

---

### Unsupported real adapter observability

Unsupported real adapter observability is surfaced in readiness and Overseer
briefs. A safe unsupported real adapter state reports
`real_adapter_supported=false`, `real_adapter_runnable=false`,
`subprocess_supported=false`, and `requires_explicit_pr=true`.

This keeps the real adapter visible to operators while preserving fail-closed
behavior until a separate explicit PR introduces real execution support.

---

Unsupported real adapter metrics are emitted as fail-closed observability values:
`security_real_adapter_supported=0`, `security_real_adapter_runnable=0`,
`security_real_adapter_subprocess_supported=0`, and
`security_real_adapter_requires_explicit_pr=1`.

---

### Real adapter threat model

Real controlled retry execution is explicitly out of scope until a separate
implementation PR enables it. The current adapter contract keeps
`real_execution_supported=false`, `subprocess_supported=false`,
`real_adapter_supported=false`, `real_adapter_runnable=false`, and
`real_adapter_requires_explicit_pr=true`.

The threat model for any future real adapter includes:

- Shell injection through command strings or unsafe argument rendering.
- Path traversal or unexpected working-directory changes.
- Environment-variable leakage or unsafe inherited process state.
- Unbounded execution time or hanging subprocesses.
- Unbounded stdout/stderr capture or log amplification.
- Executing a command that was not produced by the retry governance trail.
- Reusing stale readiness/approval evidence after the runtime state changed.
- Confusing operator authorization intent with explicit real execution approval.
- Publishing an execution result without before/after audit evidence.
- Allowing mock-readiness to imply real-readiness.

### Real adapter preflight contract

Before any real controlled retry execution can be implemented, a dedicated
preflight contract must be satisfied and surfaced in readiness, security
validation, inspector summaries, and Overseer briefs.

Required preflight gates:

- `shell=false`; `shell=True` is never allowed.
- Commands must be module-only invocations with strict argv parsing.
- The parsed module and arguments must match the controlled command allowlist.
- The working directory must be fixed and validated.
- The environment must be sanitized through an explicit allowlist.
- Timeout must use a hard cap derived from the approved timeout profile.
- stdout and stderr capture must have byte caps.
- A fresh readiness report must pass schema validation.
- The adapter contract must be observed with subprocess and real execution still disabled before approval.
- A separate explicit `real_execution_approval_id` must be present.
- Operator authorization intent alone is not sufficient for real execution.
- Audit records must be published before and after any real execution attempt.
- The real adapter must remain unsupported until the explicit implementation PR changes the adapter contract.

The current fail-closed expected state remains:

- `ready_for_mock_execution=true`
- `ready_for_real_execution=false`
- `real_execution_supported=false`
- `subprocess_supported=false`
- `real_adapter_supported=false`
- `real_adapter_runnable=false`
- `real_adapter_requires_explicit_pr=true`

---

### Real execution CLI scaffold

`run_controlled_retry_command --real-execution` is a scaffolded operator intent
flag. It does not enable real execution. Real execution requests are rejected
with `reason=real_execution_not_supported`, `real_execution_requested=true`,
`real_execution_performed=false`, `real_execution_supported=false`,
`subprocess_invoked=false`, and `payload.executed=false`.

The flag is intentionally audit-only until a separate explicit PR implements and
validates the real adapter preflight contract.

---

### Real execution request observability

Real execution request observability surfaces audit-only real execution intent.
A safe rejected real execution request reports
`real_execution_request_observed=true`, `real_execution_request_rejected=1`,
`real_execution_requested=1`, `real_execution_performed=0`,
`real_execution_supported_count=0`, and `subprocess_invoked_count=0`.

Inspector, Security, Overseer, and readiness reports must agree that the request
was observed, rejected as unsupported, and did not execute.

---

### Real execution preflight records

Real execution preflight records are read-only audit records for future real
execution requests. They are published as
`replay_lifecycle_retry_real_execution_preflight` with `status=blocked`,
`would_execute=false`, `execution_performed=false`, `subprocess_invoked=false`,
and `real_adapter_requires_explicit_pr=true`.

The preflight evaluator does not invoke subprocesses and does not make real
execution runnable. It only records why a future real execution attempt remains
blocked.

---

### Real preflight observability

Real preflight observability surfaces fail-closed preflight records in readiness
and Overseer summaries. A safe preflight reports `real_preflight_observed=true`,
`real_preflight_blocked=1`, `real_preflight_would_execute=0`,
`real_preflight_execution_performed=0`,
`real_preflight_subprocess_invoked=0`, and
`real_preflight_requires_explicit_pr=1`.

Overseer briefs report the same state as:
`Real execution preflight remains blocked`.

---

### Explicit real execution approval records

`replay_lifecycle_retry_real_execution_approval` separates operator authorization
intent from future real execution approval. The record may be pending, approved,
or rejected, but in this phase it always reports `real_execution_enabled=false`,
`subprocess_enabled=false`, `execution_performed=false`, and
`subprocess_invoked=false`.

Operator authorization alone is insufficient for real execution.

---

### Final real execution gate

`replay_lifecycle_retry_real_execution_final_gate` is the last fail-closed
gate before any future dry-run execution envelope. It requires an approved
real execution approval transition, but still reports
`ready_for_real_execution=false`, `would_execute=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`execution_performed=false`, and `subprocess_invoked=false`.

The gate remains blocked until a separate explicit execution PR enables a
supported real adapter and subprocess boundary.

---

### Real execution dry-run envelope

`replay_lifecycle_retry_real_execution_dry_run_envelope` captures the future
execution envelope without invoking subprocesses. It records argv, cwd, and a
sanitized env key list while keeping `dry_run_only=true`,
`would_execute=false`, `ready_for_real_execution=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`execution_performed=false`, and `subprocess_invoked=false`.

The envelope is an audit artifact only. It does not execute commands.

---

### Guarded noop execution harness

`replay_lifecycle_retry_real_execution_noop_result` is the first subprocess
boundary. It runs only a fixed noop command and never executes the rendered
command or the dry-run envelope command. The record must keep
`noop_only=true`, `rendered_command_executed=false`,
`dry_run_envelope_command_executed=false`, `real_execution_enabled=false`,
`subprocess_invoked=true`, `execution_performed=true`, and `exit_code=0`.

This validates subprocess plumbing without enabling real execution.

---

### Read-only evidence command promotion

`replay_lifecycle_retry_real_execution_read_only_promotion` promotes a
dry-run envelope command to a read-only candidate only after a successful
guarded noop harness result. It validates the allowlisted
`src.testing.run_replay_evidence_check` command shape while keeping
`subprocess_invoked=false`, `execution_performed=false`,
`rendered_command_executed=false`, `dry_run_envelope_command_executed=false`,
and `real_execution_enabled=false`.

Promotion is an audit/readiness artifact only. It does not execute the
read-only command. does not execute the read-only command.

---

### Read-only execution final gate

`replay_lifecycle_retry_real_execution_read_only_final_gate` is a fail-closed
gate after read-only promotion. It records that promotion preconditions were
satisfied, but keeps `gate_status=blocked`,
`ready_for_read_only_execution=false`, `read_only_execution_enabled=false`,
`subprocess_enabled=false`, `subprocess_invoked=false`,
`execution_performed=false`, `rendered_command_executed=false`, and
`dry_run_envelope_command_executed=false`.

The gate requires a separate PR before any read-only command execution can be
enabled.

---

### Read-only execution approval scaffold

`replay_lifecycle_retry_real_execution_read_only_approval` records explicit
approval intent for future read-only execution. The record may be pending,
approved, or rejected, but it must keep `read_only_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`subprocess_invoked=false`, `execution_performed=false`,
`rendered_command_executed=false`, and
`dry_run_envelope_command_executed=false`.

This approval scaffold is an audit artifact only and does not execute the
read-only command.

---

### Read-only execution approval transition

`replay_lifecycle_retry_real_execution_read_only_approval_transition` records an
immutable read-only execution approval status transition, such as
`from_status=pending` to `to_status=approved` or `to_status=rejected`.

The transition is an audit artifact only. Even when approved it must keep
`read_only_execution_enabled=false`, `real_execution_enabled=false`,
`subprocess_enabled=false`, `subprocess_invoked=false`,
`execution_performed=false`, `rendered_command_executed=false`, and
`dry_run_envelope_command_executed=false`.

---

### Read-only execution readiness gate

`replay_lifecycle_retry_real_execution_read_only_readiness_gate` is the final
pre-execution readiness artifact for guarded read-only execution. It may record
`read_only_readiness_satisfied=true` and
`ready_for_guarded_read_only_execution=true`, but it must keep
`read_only_execution_enabled=false`, `real_execution_enabled=false`,
`subprocess_enabled=false`, `subprocess_invoked=false`,
`execution_performed=false`, `rendered_command_executed=false`, and
`dry_run_envelope_command_executed=false`.

The gate remains blocked by
`guarded_read_only_execution_requires_separate_pr`.

---

### Guarded read-only execution result

`replay_lifecycle_retry_real_execution_read_only_execution_result` records the
first guarded read-only execution outcome. It is only valid for the allowlisted
`src.testing.run_replay_evidence_check` module with explicit operator
authorization and an explicit guarded read-only execution flag.

The result may be `status=executed`, `status=failed`, or `status=rejected`.
A failed exit code is still valid execution evidence when
`validation_reasons=[]`, `operator_authorized=true`,
`allow_guarded_read_only_execution=true`, `read_only_execution_enabled=true`,
`subprocess_invoked=true`, and `execution_performed=true`.

The record must keep `real_execution_enabled=false`; guarded read-only execution
does not enable arbitrary real execution.

---

### Read-only execution feedback

`replay_lifecycle_retry_real_execution_read_only_feedback` records post-execution
feedback derived from a guarded read-only execution result. A failed read-only
execution can become `feedback_status=actionable` with
`recommended_next_action=investigate_failed_read_only_evidence_check`.

The feedback record is evidence only. It must keep
`feedback_execution_performed=false`, `feedback_subprocess_invoked=false`,
`execution_performed=false`, `subprocess_invoked=false`, and
`real_execution_enabled=false`.

---

### Overseer read-only feedback recommendation

The Overseer brief surfaces
`replay_lifecycle_retry_real_execution_read_only_feedback` as an actionable
post-execution signal. When a guarded read-only execution fails, the brief should
report `feedback_status=actionable` and recommend
`investigate_failed_read_only_evidence_check`.

The recommendation is observational only. It must not perform feedback execution,
invoke subprocesses, or enable arbitrary real execution.

---

### Read-only execution repair plan

`replay_lifecycle_retry_real_execution_read_only_repair_plan` converts
actionable read-only execution feedback into a reviewable repair plan. For a
failed read-only evidence check, the plan may include targets such as
`execution_published`, `execution_completed`, `evidence_published`,
`memory_record_published`, and replay evidence visibility checks.

The repair plan is observational and review-only. It must keep
`repair_execution_enabled=false`, `real_execution_enabled=false`,
`subprocess_enabled=false`, `repair_execution_performed=false`,
`repair_subprocess_invoked=false`, `execution_performed=false`, and
`subprocess_invoked=false`.

---

### Overseer repair-plan recommendation

The Overseer brief surfaces
`replay_lifecycle_retry_real_execution_read_only_repair_plan` as a safe next
action after actionable read-only feedback. The brief should recommend
`review_replay_evidence_repair_plan` and summarize repair targets before any
future execution expansion.

This recommendation is review-only. It must keep
`repair_execution_enabled=false`, `real_execution_enabled=false`,
`subprocess_enabled=false`, `repair_execution_performed=false`, and
`repair_subprocess_invoked=false`.

---

### Read-only repair action bundle

`replay_lifecycle_retry_real_execution_read_only_repair_action_bundle` converts
a reviewable repair plan into a structured action bundle. The bundle lists
candidate repair actions and targets, but it remains review-only until a later
explicit approval and execution PR.

The bundle must keep `bundle_reviewed=false`,
`bundle_execution_enabled=false`, `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`bundle_execution_performed=false`, `bundle_subprocess_invoked=false`,
`execution_performed=false`, and `subprocess_invoked=false`.

---

### Overseer repair action bundle recommendation

The Overseer brief surfaces
`replay_lifecycle_retry_real_execution_read_only_repair_action_bundle` as the
next review gate after a repair plan is assembled. The brief should recommend
`review_repair_action_bundle` before any repair execution approval or execution
expansion.

This recommendation is review-only. It must keep `bundle_reviewed=false`,
`bundle_execution_enabled=false`, `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`bundle_execution_performed=false`, and `bundle_subprocess_invoked=false`.

---

### Repair action bundle operator review

`replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review`
records explicit operator review of a repair action bundle. An approved review
may recommend `prepare_repair_execution_approval_scaffold`, but it must not
enable or perform execution.

The review artifact must keep `bundle_execution_enabled=false`,
`repair_execution_enabled=false`, `real_execution_enabled=false`,
`subprocess_enabled=false`, `bundle_execution_performed=false`,
`bundle_subprocess_invoked=false`, `execution_performed=false`, and
`subprocess_invoked=false`. must not enable or perform execution.

---

### Overseer repair review recommendation

The Overseer brief surfaces approved
`replay_lifecycle_retry_real_execution_read_only_repair_action_bundle_review`
records and recommends `prepare_repair_execution_approval_scaffold`.

This recommendation prepares the next approval artifact only. It must keep
`repair_execution_enabled=false`, `real_execution_enabled=false`,
`subprocess_enabled=false`, `execution_performed=false`, and
`subprocess_invoked=false`.

---

### Repair execution approval scaffold

`replay_lifecycle_retry_real_execution_repair_approval` records an explicit
repair execution approval scaffold after an approved repair action bundle review.
The scaffold may be `pending`, `approved`, or `rejected`, but it must not enable
or perform repair execution.

The approval scaffold must keep `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`repair_execution_performed=false`, `repair_subprocess_invoked=false`,
`execution_performed=false`, and `subprocess_invoked=false`. must not enable or perform repair execution.

---

### Repair execution approval transition

`replay_lifecycle_retry_real_execution_repair_approval_transition` records an
immutable transition from a pending repair execution approval to `approved` or
`rejected`. An approved transition may recommend
`prepare_repair_execution_final_gate`, but it must not enable or perform repair
execution.

The transition artifact must keep `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`repair_execution_performed=false`, `repair_subprocess_invoked=false`,
`execution_performed=false`, and `subprocess_invoked=false`.

---

### Repair execution final gate

`replay_lifecycle_retry_real_execution_repair_final_gate` records the final
pre-dry-run gate after an approved repair execution approval transition. A
`ready_blocked` gate may recommend `prepare_repair_execution_dry_run_envelope`,
but it must not enable or perform repair execution.

The final gate artifact must keep `ready_for_repair_execution=false`,
`would_execute=false`, `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`repair_execution_performed=false`, `repair_subprocess_invoked=false`,
`execution_performed=false`, and `subprocess_invoked=false`.

---

### Repair execution dry-run envelope

`replay_lifecycle_retry_real_execution_repair_dry_run_envelope` records the
dry-run envelope after a ready-blocked repair execution final gate. The envelope
captures the repair action bundle targets and validation mode, but it must not
apply changes, execute the bundle, invoke subprocesses, or enable repair
execution.

The dry-run envelope artifact must keep `dry_run_only=true`,
`ready_for_repair_execution=false`, `would_execute=false`,
`repair_execution_enabled=false`, `real_execution_enabled=false`,
`subprocess_enabled=false`, `repair_execution_performed=false`,
`repair_subprocess_invoked=false`, `execution_performed=false`, and
`subprocess_invoked=false`. must not apply changes.

---

### Repair execution noop harness

`replay_lifecycle_retry_real_execution_repair_noop_result` records a controlled
noop subprocess after a prepared repair execution dry-run envelope. The noop
harness may set `execution_performed=true` and `subprocess_invoked=true` only
for the controlled noop marker, but it must not execute repair actions, execute
the repair bundle, execute the repair command, or enable repair execution.

The noop result artifact must keep `noop_only=true`,
`repair_actions_executed=false`, `repair_bundle_executed=false`,
`repair_command_executed=false`, `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`repair_execution_performed=false`, and `repair_subprocess_invoked=false`. controlled noop subprocess.

---

### Repair noop feedback

`replay_lifecycle_retry_real_execution_repair_noop_feedback` records the
decision after a completed repair noop result. An actionable feedback record may
allow the next readiness gate with
`recommended_next_action=prepare_repair_execution_readiness_gate`, but it must
not execute feedback logic via subprocess and must not enable repair execution.

The feedback artifact must keep `feedback_execution_performed=false`,
`feedback_subprocess_invoked=false`, `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`repair_execution_performed=false`, `repair_subprocess_invoked=false`,
`execution_performed=false`, and `subprocess_invoked=false`. must not execute feedback logic via subprocess.

---

### Repair execution readiness gate

`replay_lifecycle_retry_real_execution_repair_readiness_gate` records that the
repair path is ready for a later guarded repair execution harness after
actionable repair noop feedback. The gate may set
`ready_for_guarded_repair_execution=true`, but it remains `ready_blocked` and
must keep `ready_for_repair_execution=false` until a separate guarded execution
PR is implemented.

The readiness gate must keep `repair_execution_enabled=false`,
`real_execution_enabled=false`, `subprocess_enabled=false`,
`repair_execution_performed=false`, `repair_subprocess_invoked=false`,
`execution_performed=false`, and `subprocess_invoked=false`.

---

### Guarded repair execution result

`replay_lifecycle_retry_guarded_repair_execution_result` records the first
guarded repair execution outcome after a satisfied repair readiness gate. It is
valid only after the repair path has passed explicit approval, dry-run envelope,
noop harness, noop feedback, and readiness lineage.

A successful guarded repair execution result reports:

```text
repair_execution_status=succeeded
repair_execution_allowed=true
guarded_repair_marker_observed=true
exit_code=0
repair_action_target_count=9
repair_actions_executed=true
repair_bundle_executed=true
repair_command_executed=true
recommended_next_action=run_post_repair_evidence_check
```

The guarded repair harness is still a controlled harness, not arbitrary real
execution. It must keep:

```text
real_execution_enabled=false
rendered_command_executed=false
dry_run_command_executed=false
```

The result may enable and perform only the guarded repair harness subprocess:

```text
repair_execution_enabled=true
subprocess_enabled=true
repair_execution_performed=true
repair_subprocess_invoked=true
execution_performed=true
subprocess_invoked=true
```

Security, inspector, readiness, and Overseer metrics must surface the guarded
repair execution result before the loop can be considered ready for post-repair
verification.

---

### Verified guarded repair loop

The full verified repair loop is closed only when the post-repair evidence check
passes after a succeeded guarded repair execution result.

Expected final verification signals:

```text
post_repair_status=passed
post_repair_evidence_check_allowed=true
post_repair_evidence_check_enabled=true
post_repair_evidence_marker_observed=true
post_repair_evidence_exit_code=0
repair_outcome_verified=true
repair_targets_expected_count=9
repair_targets_verified_count=9
repair_targets_missing=[]
repair_targets_unexpected=[]
source_guarded_repair_execution_status=succeeded
source_guarded_repair_execution_allowed=true
source_guarded_repair_marker_observed=true
source_guarded_repair_exit_code=0
source_guarded_repair_next_action=run_post_repair_evidence_check
recommended_next_action=close_repair_loop
```

The post-repair evidence check may execute only the verification subprocess. It
must not perform another repair execution:

```text
repair_execution_enabled=false
real_execution_enabled=false
repair_execution_performed=false
repair_subprocess_invoked=false
```

This gives the runtime an auditable path from failed read-only evidence to
reviewed repair, guarded repair execution, verified outcome, and
`close_repair_loop`.

---

### Post-repair evidence check

`replay_lifecycle_retry_post_repair_evidence_check` records the final
verification after a succeeded guarded repair execution result. A passed check
requires the post-repair marker, zero evidence-check exit code, all expected
repair targets verified, and no missing or unexpected targets.

This artifact may execute only the evidence-check subprocess. It must keep
`repair_execution_enabled=false`, `real_execution_enabled=false`,
`repair_execution_performed=false`, and `repair_subprocess_invoked=false`.
A passed check recommends `close_repair_loop`.

Security validation, the governance trail inspector, the controlled execution
readiness report, and Overseer summaries must agree on the final verified state:
`post_repair_status=passed`, `repair_outcome_verified=true`,
`repair_targets_verified_count=9`, no missing or unexpected targets, and
`recommended_next_action=close_repair_loop`.

---

### Sandbox adapter scaffold observability check

`src.testing.check_sandbox_adapter_scaffold_observability` is a read-only helper
that verifies fail-closed sandbox adapter scaffold visibility through Security,
Inspector, Readiness-style gates, and Overseer brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold observed
Security record type count > 0
Inspector scaffold linkage complete
sandbox scaffold orphans = 0
sandbox_adapter_scaffold_status=defined
sandbox_adapter_fail_closed=true
sandbox_adapter_deny_by_default=true
sandbox_execution_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```

---

### Sandbox adapter request preflight scaffold

`src.testing.build_real_execution_sandbox_adapter_request_preflight` builds the
next fail-closed scaffold after the sandbox adapter scaffold has been observed by
Security, Inspector, Readiness, and Overseer.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight
```
This artifact is still read-only and blocked. It does not generate executable
sandbox adapter requests, create workspaces, materialize inputs, render commands,
run sandbox execution, generate results, invoke subprocesses, or enable real
execution.

Expected safe fields include:

```text
sandbox_adapter_request_preflight_status=blocked
sandbox_adapter_request_preflight_fail_closed=true
sandbox_adapter_request_preflight_deny_by_default=true
sandbox_adapter_request_generation_enabled=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```

---

### Sandbox adapter request preflight observability check

`src.testing.check_sandbox_adapter_request_preflight_observability` is a
read-only helper that verifies fail-closed sandbox adapter request preflight
visibility through Security, Inspector, Readiness-style gates, and Overseer
brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight observed
Security record type count > 0
Inspector request preflight linkage complete
sandbox request preflight orphans = 0
sandbox_adapter_request_preflight_status=blocked
sandbox_adapter_request_preflight_fail_closed=true
sandbox_adapter_request_preflight_deny_by_default=true
sandbox_adapter_request_generation_enabled=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```

Runtime command:

```bash
python -m src.testing.check_sandbox_adapter_request_preflight_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db

This check does not generate sandbox requests, create workspaces, materialize
inputs, render commands, execute sandbox commands, invoke subprocesses, or enable
real execution.
```
---

### Sandbox request envelope scaffold

`src.testing.build_real_execution_sandbox_request_envelope_scaffold` builds the
next blocked artifact after sandbox adapter request preflight observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_request_envelope_scaffold
```
This artifact is still read-only and blocked. It does not generate executable
sandbox requests, create workspaces, materialize inputs, render commands, execute
sandbox commands, generate results, invoke subprocesses, or enable real
execution.

Expected safe fields include:
```text
sandbox_request_envelope_scaffold_status=blocked
sandbox_request_envelope_scaffold_fail_closed=true
sandbox_request_envelope_scaffold_deny_by_default=true
sandbox_request_envelope_generation_enabled=false
sandbox_request_envelope_materialized=false
sandbox_request_envelope_executable=false
sandbox_adapter_request_generation_enabled=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_request_envelope_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox request envelope scaffold observability check

`src.testing.check_sandbox_request_envelope_scaffold_observability` is a
read-only helper that verifies fail-closed sandbox request envelope scaffold
visibility through Security, Inspector, Readiness-style gates, and Overseer
brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_request_envelope_scaffold observed
Security record type count > 0
Inspector envelope scaffold linkage complete
sandbox request envelope scaffold orphans = 0
sandbox_request_envelope_scaffold_status=blocked
sandbox_request_envelope_scaffold_fail_closed=true
sandbox_request_envelope_scaffold_deny_by_default=true
sandbox_request_envelope_generation_enabled=false
sandbox_request_envelope_materialized=false
sandbox_request_envelope_executable=false
sandbox_adapter_request_generation_enabled=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.check_sandbox_request_envelope_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not generate sandbox request envelopes, materialize envelopes,
create workspaces, materialize inputs, render commands, execute sandbox
commands, invoke subprocesses, or enable real execution.

---

### Sandbox materialization preflight scaffold

`src.testing.build_real_execution_sandbox_materialization_preflight_scaffold`
builds the next blocked artifact after sandbox request envelope scaffold
observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_materialization_preflight_scaffold
```
This artifact is still read-only and blocked. It does not generate sandbox
request envelopes, materialize envelopes, create workspaces, materialize inputs,
render commands, execute sandbox commands, generate results, invoke subprocesses,
or enable real execution.

Expected safe fields include:
```text
sandbox_materialization_preflight_scaffold_status=blocked
sandbox_materialization_preflight_scaffold_fail_closed=true
sandbox_materialization_preflight_scaffold_deny_by_default=true
sandbox_materialization_preflight_allowed=false
sandbox_materialization_preflight_enabled=false
sandbox_materialization_preflight_passed=false
sandbox_request_envelope_generation_enabled=false
sandbox_request_envelope_materialized=false
sandbox_request_envelope_executable=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_materialization_preflight_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox materialization preflight scaffold observability check

`src.testing.check_sandbox_materialization_preflight_scaffold_observability`
is a read-only helper that verifies fail-closed sandbox materialization
preflight scaffold visibility through Security, Inspector, Readiness-style
gates, and Overseer brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_materialization_preflight_scaffold observed
Security record type count > 0
Inspector materialization preflight scaffold linkage complete
sandbox materialization preflight scaffold orphans = 0
sandbox_materialization_preflight_scaffold_status=blocked
sandbox_materialization_preflight_scaffold_fail_closed=true
sandbox_materialization_preflight_scaffold_deny_by_default=true
sandbox_materialization_preflight_enabled=false
sandbox_materialization_preflight_passed=false
sandbox_request_envelope_generation_enabled=false
sandbox_request_envelope_materialized=false
sandbox_request_envelope_executable=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.check_sandbox_materialization_preflight_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not enable materialization preflight, pass materialization
preflight, generate or materialize envelopes, create workspaces, materialize
inputs, render commands, execute sandbox commands, invoke subprocesses, or
enable real execution.

---

### Sandbox workspace plan scaffold

`src.testing.build_real_execution_sandbox_workspace_plan_scaffold` builds the
next blocked artifact after sandbox materialization preflight scaffold
observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_workspace_plan_scaffold
```
This artifact is still read-only and blocked. It does not enable
materialization preflight, pass materialization preflight, generate or
materialize envelopes, generate executable workspace plans, create workspaces,
materialize inputs, render commands, execute sandbox commands, generate results,
invoke subprocesses, or enable real execution.

Expected safe fields include:
```text
sandbox_workspace_plan_scaffold_status=blocked
sandbox_workspace_plan_scaffold_fail_closed=true
sandbox_workspace_plan_scaffold_deny_by_default=true
sandbox_workspace_plan_generation_enabled=false
sandbox_workspace_plan_materialized=false
sandbox_workspace_plan_executable=false
sandbox_workspace_directory_creation_enabled=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_materialization_preflight_enabled=false
sandbox_materialization_preflight_passed=false
sandbox_request_envelope_generation_enabled=false
sandbox_request_envelope_materialized=false
sandbox_request_envelope_executable=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_workspace_plan_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox workspace plan scaffold observability check

`src.testing.check_sandbox_workspace_plan_scaffold_observability` is a
read-only helper that verifies fail-closed sandbox workspace plan scaffold
visibility through Security, Inspector, Readiness-style gates, and Overseer
brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_workspace_plan_scaffold observed
Security record type count > 0
Inspector workspace plan scaffold linkage complete
sandbox workspace plan scaffold orphans = 0
sandbox_workspace_plan_scaffold_status=blocked
sandbox_workspace_plan_scaffold_fail_closed=true
sandbox_workspace_plan_scaffold_deny_by_default=true
sandbox_workspace_plan_generation_enabled=false
sandbox_workspace_plan_materialized=false
sandbox_workspace_plan_executable=false
sandbox_workspace_directory_creation_enabled=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_materialization_preflight_enabled=false
sandbox_materialization_preflight_passed=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.check_sandbox_workspace_plan_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not generate workspace plans, materialize plans, create
directories, create workspaces, register cleanup, materialize inputs, render
commands, execute sandbox commands, invoke subprocesses, or enable real
execution.

---

### Sandbox workspace preparation preflight scaffold

`src.testing.build_real_execution_sandbox_workspace_preparation_preflight_scaffold`
builds the next blocked artifact after sandbox workspace plan scaffold
observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_workspace_preparation_preflight_scaffold
```
This artifact is still read-only and blocked. It does not generate workspace
plans, materialize workspace plans, enable workspace preparation preflight, pass
workspace preparation preflight, create directories, create workspaces, register
cleanup, materialize inputs, render commands, execute sandbox commands, generate
results, invoke subprocesses, or enable real execution.

Expected safe fields include:
```text
sandbox_workspace_preparation_preflight_scaffold_status=blocked
sandbox_workspace_preparation_preflight_scaffold_fail_closed=true
sandbox_workspace_preparation_preflight_scaffold_deny_by_default=true
sandbox_workspace_preparation_preflight_enabled=false
sandbox_workspace_preparation_preflight_passed=false
sandbox_workspace_plan_generation_enabled=false
sandbox_workspace_plan_materialized=false
sandbox_workspace_plan_executable=false
sandbox_workspace_directory_creation_enabled=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_workspace_preparation_preflight_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox workspace preparation preflight scaffold observability check

`src.testing.check_sandbox_workspace_preparation_preflight_scaffold_observability`
is a read-only helper that verifies fail-closed sandbox workspace preparation
preflight scaffold visibility through Security, Inspector, Readiness-style gates,
and Overseer brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_workspace_preparation_preflight_scaffold observed
Security record type count > 0
Inspector workspace preparation preflight scaffold linkage complete
sandbox workspace preparation preflight scaffold orphans = 0
sandbox_workspace_preparation_preflight_scaffold_status=blocked
sandbox_workspace_preparation_preflight_scaffold_fail_closed=true
sandbox_workspace_preparation_preflight_scaffold_deny_by_default=true
sandbox_workspace_preparation_preflight_enabled=false
sandbox_workspace_preparation_preflight_passed=false
sandbox_workspace_plan_generation_enabled=false
sandbox_workspace_plan_materialized=false
sandbox_workspace_plan_executable=false
sandbox_workspace_directory_creation_enabled=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```text
python -m src.testing.check_sandbox_workspace_preparation_preflight_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not enable workspace preparation preflight, pass workspace
preparation preflight, create directories, create workspaces, register cleanup,
materialize inputs, render commands, execute sandbox commands, invoke
subprocesses, or enable real execution.

---

### Sandbox input materialization plan scaffold

`src.testing.build_real_execution_sandbox_input_materialization_plan_scaffold`
builds the next blocked artifact after sandbox workspace preparation preflight
scaffold observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_input_materialization_plan_scaffold
```
This artifact is still read-only and blocked. It does not enable workspace
preparation preflight, pass workspace preparation preflight, create directories,
create workspaces, register cleanup, generate input materialization plans,
materialize input materialization plans, materialize inputs, render commands,
execute sandbox commands, generate results, invoke subprocesses, or enable real
execution.

Expected safe fields include:
```text
sandbox_input_materialization_plan_scaffold_status=blocked
sandbox_input_materialization_plan_scaffold_fail_closed=true
sandbox_input_materialization_plan_scaffold_deny_by_default=true
sandbox_input_materialization_plan_generation_enabled=false
sandbox_input_materialization_plan_materialized=false
sandbox_input_materialization_plan_executable=false
sandbox_input_materialization_enabled=false
sandbox_inputs_materialized=false
sandbox_workspace_preparation_preflight_enabled=false
sandbox_workspace_preparation_preflight_passed=false
sandbox_workspace_directory_creation_enabled=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_workspace_creation_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_input_materialization_plan_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox input materialization plan scaffold observability check

`src.testing.check_sandbox_input_materialization_plan_scaffold_observability`
is a read-only helper that verifies fail-closed sandbox input materialization plan
scaffold visibility through Security, Inspector, Readiness-style gates, and
Overseer brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_input_materialization_plan_scaffold observed
Security record type count > 0
Inspector input materialization plan scaffold linkage complete
sandbox input materialization plan scaffold orphans = 0
sandbox_input_materialization_plan_scaffold_status=blocked
sandbox_input_materialization_plan_scaffold_fail_closed=true
sandbox_input_materialization_plan_scaffold_deny_by_default=true
sandbox_input_materialization_plan_generation_enabled=false
sandbox_input_materialization_plan_materialized=false
sandbox_input_materialization_plan_executable=false
sandbox_input_materialization_enabled=false
sandbox_inputs_materialized=false
sandbox_workspace_preparation_preflight_enabled=false
sandbox_workspace_preparation_preflight_passed=false
sandbox_workspace_directory_creation_enabled=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_workspace_creation_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.check_sandbox_input_materialization_plan_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not generate input materialization plans, materialize plans,
materialize inputs, render commands, execute sandbox commands, invoke
subprocesses, or enable real execution.

---

### Sandbox command render plan scaffold

`src.testing.build_real_execution_sandbox_command_render_plan_scaffold`
builds the next blocked artifact after sandbox input materialization plan scaffold
observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_command_render_plan_scaffold
```
This artifact is still read-only and blocked. It does not generate command
render plans, materialize command render plans, render sandbox commands, validate
rendered sandbox commands, materialize inputs, execute sandbox commands, generate
results, invoke subprocesses, or enable real execution.

Expected safe fields include:
```text
sandbox_command_render_plan_scaffold_status=blocked
sandbox_command_render_plan_scaffold_fail_closed=true
sandbox_command_render_plan_scaffold_deny_by_default=true
sandbox_command_render_plan_generation_enabled=false
sandbox_command_render_plan_materialized=false
sandbox_command_render_plan_executable=false
sandbox_command_rendering_enabled=false
sandbox_command_rendered=false
sandbox_rendered_command_validated=false
sandbox_input_materialization_plan_generation_enabled=false
sandbox_input_materialization_plan_materialized=false
sandbox_input_materialization_plan_executable=false
sandbox_input_materialization_enabled=false
sandbox_inputs_materialized=false
sandbox_workspace_preparation_preflight_enabled=false
sandbox_workspace_preparation_preflight_passed=false
sandbox_workspace_directory_creation_enabled=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_workspace_creation_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_command_render_plan_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox command render plan scaffold observability check

`src.testing.check_sandbox_command_render_plan_scaffold_observability`
is a read-only helper that verifies fail-closed sandbox command render plan
scaffold visibility through Security, Inspector, Readiness-style gates, and
Overseer brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_command_render_plan_scaffold observed
Security record type count > 0
Inspector command render plan scaffold linkage complete
sandbox command render plan scaffold orphans = 0
sandbox_command_render_plan_scaffold_status=blocked
sandbox_command_render_plan_scaffold_fail_closed=true
sandbox_command_render_plan_scaffold_deny_by_default=true
sandbox_command_render_plan_generation_enabled=false
sandbox_command_render_plan_materialized=false
sandbox_command_render_plan_executable=false
sandbox_command_rendering_enabled=false
sandbox_command_rendered=false
sandbox_rendered_command_validated=false
sandbox_execution_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
```
Runtime command:
```bash
python -m src.testing.check_sandbox_command_render_plan_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not generate command render plans, materialize command render
plans, render sandbox commands, validate rendered commands, execute sandbox
commands, invoke subprocesses, or enable real execution.

---

### Sandbox rendered command scaffold

`src.testing.build_real_execution_sandbox_rendered_command_scaffold`
builds the next blocked artifact after sandbox command render plan scaffold
observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_rendered_command_scaffold
```
This artifact is still read-only and blocked. It does not generate rendered
commands, materialize rendered commands, validate rendered commands, render
sandbox commands, execute sandbox commands, generate results, invoke
subprocesses, or enable real execution.

Expected safe fields include:
```text
sandbox_rendered_command_scaffold_status=blocked
sandbox_rendered_command_scaffold_fail_closed=true
sandbox_rendered_command_scaffold_deny_by_default=true
sandbox_rendered_command_generation_enabled=false
sandbox_rendered_command_materialized=false
sandbox_rendered_command_executable=false
sandbox_rendered_command_validated=false
sandbox_command_render_plan_generation_enabled=false
sandbox_command_render_plan_materialized=false
sandbox_command_render_plan_executable=false
sandbox_command_rendering_enabled=false
sandbox_command_rendered=false
sandbox_input_materialization_plan_generation_enabled=false
sandbox_input_materialization_plan_materialized=false
sandbox_input_materialization_plan_executable=false
sandbox_input_materialization_enabled=false
sandbox_inputs_materialized=false
sandbox_workspace_created=false
sandbox_workspace_cleanup_registered=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_rendered_command_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox rendered command scaffold observability check

`src.testing.check_sandbox_rendered_command_scaffold_observability`
is a read-only helper that verifies fail-closed sandbox rendered command scaffold
visibility through Security, Inspector, Readiness-style gates, and Overseer brief
metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_rendered_command_scaffold observed
Security record type count > 0
Inspector rendered command scaffold linkage complete
sandbox rendered command scaffold orphans = 0
sandbox_rendered_command_scaffold_status=blocked
sandbox_rendered_command_scaffold_fail_closed=true
sandbox_rendered_command_scaffold_deny_by_default=true
sandbox_rendered_command_generation_enabled=false
sandbox_rendered_command_materialized=false
sandbox_rendered_command_executable=false
sandbox_rendered_command_validated=false
sandbox_command_render_plan_generation_enabled=false
sandbox_command_render_plan_materialized=false
sandbox_command_render_plan_executable=false
sandbox_command_rendering_enabled=false
sandbox_command_rendered=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
```
Runtime command:
```bash
python -m src.testing.check_sandbox_rendered_command_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not generate rendered commands, materialize rendered commands,
validate rendered commands, execute sandbox commands, invoke subprocesses, or
enable real execution.

---

### Sandbox rendered command validation scaffold

`src.testing.build_real_execution_sandbox_rendered_command_validation_scaffold`
builds the next blocked artifact after sandbox rendered command scaffold
observability.

The record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_rendered_command_validation_scaffold
```
This artifact is still read-only and blocked. It does not validate rendered
commands, mark rendered commands executable, generate rendered commands,
materialize rendered commands, execute sandbox commands, generate results, invoke
subprocesses, or enable real execution.

Expected safe fields include:
```text
sandbox_rendered_command_validation_scaffold_status=blocked
sandbox_rendered_command_validation_scaffold_fail_closed=true
sandbox_rendered_command_validation_scaffold_deny_by_default=true
sandbox_rendered_command_validation_enabled=false
sandbox_rendered_command_validation_performed=false
sandbox_rendered_command_validation_passed=false
sandbox_rendered_command_validation_failed=false
sandbox_rendered_command_generation_enabled=false
sandbox_rendered_command_materialized=false
sandbox_rendered_command_executable=false
sandbox_rendered_command_validated=false
sandbox_command_render_plan_generation_enabled=false
sandbox_command_render_plan_materialized=false
sandbox_command_render_plan_executable=false
sandbox_command_rendering_enabled=false
sandbox_command_rendered=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```
Runtime command:
```bash
python -m src.testing.build_real_execution_sandbox_rendered_command_validation_scaffold \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

---

### Sandbox rendered command validation scaffold observability check

`src.testing.check_sandbox_rendered_command_validation_scaffold_observability`
is a read-only helper that verifies fail-closed sandbox rendered command
validation scaffold visibility through Security, Inspector, Readiness-style
gates, and Overseer brief metrics.

The check requires:

```text
replay_lifecycle_retry_real_execution_sandbox_rendered_command_validation_scaffold observed
Security record type count > 0
Inspector rendered command validation scaffold linkage complete
sandbox rendered command validation scaffold orphans = 0
sandbox_rendered_command_validation_scaffold_status=blocked
sandbox_rendered_command_validation_scaffold_fail_closed=true
sandbox_rendered_command_validation_scaffold_deny_by_default=true
sandbox_rendered_command_validation_enabled=false
sandbox_rendered_command_validation_performed=false
sandbox_rendered_command_validation_passed=false
sandbox_rendered_command_validation_failed=false
sandbox_rendered_command_generation_enabled=false
sandbox_rendered_command_materialized=false
sandbox_rendered_command_executable=false
sandbox_rendered_command_validated=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
```
Runtime command:
```text
python -m src.testing.check_sandbox_rendered_command_validation_scaffold_observability \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```
This check does not validate rendered commands, mark rendered commands executable,
execute sandbox commands, invoke subprocesses, or enable real execution.

---

## Sandbox execution substrate closure

The sandbox execution substrate is now considered complete enough to serve as a
reusable reference contour for other swarms.

The completed contour includes fail-closed records and observability for:

```text
real execution adapter contract
real execution adapter request schema
capability policy matrix
sandbox adapter scaffold
sandbox adapter request preflight
sandbox request envelope scaffold
sandbox materialization preflight scaffold
sandbox workspace plan scaffold
sandbox workspace preparation preflight scaffold
sandbox input materialization plan scaffold
sandbox command render plan scaffold
sandbox rendered command scaffold
sandbox rendered command validation scaffold
```

This contour intentionally stops before actual sandbox execution. The final
completed state verifies:

```text
sandbox_rendered_command_validation_scaffold_observed=true
sandbox_rendered_command_validation_scaffold_linkage_complete=true
sandbox_rendered_command_validation_scaffold_orphans=0
sandbox_rendered_command_validation_scaffold_status=blocked
sandbox_rendered_command_validation_scaffold_fail_closed=true
sandbox_rendered_command_validation_scaffold_deny_by_default=true
sandbox_rendered_command_validation_enabled=false
sandbox_rendered_command_validation_performed=false
sandbox_rendered_command_validation_passed=false
sandbox_rendered_command_validation_failed=false
sandbox_rendered_command_executable=false
sandbox_rendered_command_validated=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```

Future work should avoid expanding this contour unless a new dangerous execution
class requires extra preflight evidence. Normal swarm development should now use
this substrate as a reference and move toward controlled execution.

### Execution risk tiers

Execution capabilities should be grouped by risk tier:

```text
safe_local_execution
  Local sandbox-only commands.
  May run allowlisted subprocesses.
  May write only inside an ephemeral sandbox workspace.
  Must not access secrets, production paths, network writes, wallets, or external APIs.

testnet_external_write
  Real external execution on testnets only.
  Includes Sepolia trading/swaps with test wallets and explicit testnet configuration.
  Does not require simulation by default, but still requires capability policy,
  explicit network identity, budget/cap limits, and operator visibility.

network_read
  Internet or API reads.
  Used by explorer/data-gathering swarms.
  Requires rate limits, source attribution, and storage boundaries.

external_write_stub
  Non-testnet external writes such as posting messages, modifying GitHub,
  sending email, or writing to third-party APIs.
  Stubbed until explicitly approved per capability.

production_financial_write
  Mainnet swaps, transfers, approvals, CEX orders, withdrawals, leverage, or
  irreversible financial actions.
  Must remain blocked until separate explicit approval and production policy.

system_dangerous_stub
  Host-destructive or production-destructive operations such as rm outside
  sandbox, chmod/chown, service restart, docker control, package installation,
  credential access, or production database mutation.
  Stubbed unless explicitly approved in a dedicated safety PR.
```

### Transition rule

The next development phase should prefer useful execution and swarm behavior over
more scaffold expansion. Additional readiness/observability contours should only
be added for dangerous capabilities, production writes, secrets, financial
mainnet actions, or host-destructive operations.

Recommended next swarm targets:

```text
explorer
  Internet/data collection, source discovery, evidence extraction, crawling
  policy, freshness ranking, and handoff to memory.

memory
  Ingestion, normalization, deduplication, classification, storage, retrieval,
  retention, and evidence routing for all swarms.
```
---

## Explorer Network-Read Evidence Loop

The Explorer swarm now has a verified `network_read` execution path that can turn an explicit research/evidence seed into structured memory.

Verified path:

```text
research goal
  -> evidence seed target
  -> explorer_targets
  -> explorer node network_read fetch
  -> explorer_finding
  -> explorer meta-agent classification
  -> USEFUL finding
  -> memory handoff quality gate
  -> memory_record
```

The verified runtime contract is intentionally read-only:

```text
execution_risk_tier=network_read
network_read_candidate=true
network_read_performed=true
external_write_performed=false
real_execution_enabled=false
production_paths_mutated=false
production_secrets_accessed=false
```

The first verified runtime loop used an explicit evidence seed URL and produced at least one `memory_record` from Explorer output.

Expected success signals:

```text
source_adapter_targets_seen.evidence_seed >= 1
source_adapter_targets_selected.evidence_seed >= 1
findings_emitted > 0
classifications_published > 0
memory_records_published > 0
total_memory_records_published > 0
```

This closes the first useful Explorer execution bridge:

```text
goal/evidence seed -> network read -> finding -> USEFUL -> memory_record
```

The loop does not enable external writes. It only reads public network sources under source policy, rate limits, robots handling, quality gates, and CRDT audit records.

Important implementation notes:

* evidence seed targets may be re-ingested across exploration runs even if the URL was seen before;
* evidence seed metadata is propagated into finding provenance;
* meta-agent classification preserves evidence payload fields such as URL, domain, content hash, fetch status, and content preview;
* missing or empty previews can be repaired for evidence-seed memory handoff through metadata-derived preview fallback;
* placeholder domains such as `example.com` remain blocked from memory handoff;
* short-preview GitHub/search/root pages may be classified as useful candidates but still rejected by memory quality gates until a stronger evidence preview exists.

This loop is now the canonical starting point for Explorer-to-Memory execution work. Future Explorer improvements should extend the research planner and source discovery path so that the system can generate high-priority evidence seeds from a research goal without manual URL seeding.

---

### Explorer source-planned evidence loop contract

The source-planned explorer runtime contract validates more than successful execution.
It also checks that the loop produces useful evidence safely.

The checker verifies:

- the requested ticks completed;
- no external writes were performed;
- real execution remained disabled;
- production paths and secrets were not touched;
- enough findings and targets were produced;
- enough `explorer_useful_evidence` memory records were published;
- evidence targets were seen and selected by the node scheduler;
- source-adapter rate limits are reported as telemetry, not treated as fatal failures.

Safe rate-limit telemetry currently includes:

- `robots_disallowed`
- `domain_window_rate_limited`
- `http_429`
- `policy_blocked`

---

### Memory swarm ingestion candidates

Explorer useful evidence records are normalized before entering local memory.

The memory ingestion contract converts:

```text
explorer memory_record(record_kind=explorer_useful_evidence)
→ memory_ingest_candidate
→ LocalMemory-compatible evidence record
```
The candidate contract preserves URL, domain, content preview, evidence scores,
topic tags, category, dedupe key, and source provenance.

The ingestion path remains advisory and dataflow-only:

- no external writes;
- no real execution;
- no production path mutation;
- no production secrets access.

---

### Memory evidence catalog

Memory ingestion candidates can be normalized into catalog/index-ready evidence
items.

The catalog layer converts:

```text
memory_ingest_candidate
→ memory_evidence_catalog_item
→ memory_evidence_catalog
```
The catalog indexes evidence by:

- domain;
- evidence category;
- topic tags;
- dedupe key;
- deterministic ranking score.

This layer is still local/dataflow-only. It performs no external writes, does not
enable real execution, does not mutate production paths, and does not access
production secrets.

---

### Memory catalog heartbeat telemetry

Memory swarm heartbeats report evidence catalog telemetry derived from local
memory evidence records.

The heartbeat metrics include:

- `evidence_catalog_items`
- `evidence_catalog_rejected_items`
- `evidence_catalog_domains`
- `evidence_catalog_categories`
- `evidence_catalog_topic_tags`
- `evidence_catalog_top_items`

This telemetry is local and dataflow-only. It performs no external writes, does
not enable real execution, does not mutate production paths, and does not access
production secrets.

---

### Memory evidence catalog retrieval

Memory evidence catalog retrieval is deterministic and local-only.

The query contract filters catalog items by:

- exact normalized domain;
- exact evidence category;
- required topic tags;
- text query terms across URL, domain, summary, preview, category, and tags;
- minimum ranking score;
- result limit.

Query results are sorted by ranking score, relevance, source score, text match,
domain, and URL.

The retrieval layer performs no external writes, does not enable real execution,
does not mutate production paths, and does not access production secrets.

---

### Memory evidence catalog query CLI

The memory evidence catalog query CLI provides a testing-only way to inspect
local memory evidence records without running a full swarm loop.

Example:

```bash
python -m src.testing.query_memory_evidence_catalog \
  --text-query "agents memory" \
  --limit 5 \
  --json
```
The CLI builds a local memory_evidence_catalog, applies deterministic filters,
and returns memory_evidence_query_result.

It performs no external writes, does not enable real execution, does not mutate
production paths, and does not access production secrets.

---

### Cluster CLI evidence profiles

The local cluster CLI includes evidence-oriented development profiles:

- `full-safe` — preserves the existing safe local cluster defaults;
- `explorer-evidence` — starts explorer node/meta without trade/security services;
- `memory-evidence` — starts memory node(s) for local evidence ingestion and catalog telemetry;
- `explorer-memory-evidence` — starts explorer node/meta plus memory node(s).

The profiles are advisory and safe by default. They force dry-run/no-execution
settings unless the operator explicitly chooses unsafe mode.

The cluster CLI also exposes a `memory-query` helper that prints the testing
command for deterministic local memory evidence catalog queries.

---

### Safe public search query templates

Explorer source planning can generate safe public search templates for
allowlisted public sources.

Allowed source sites include:

- `arxiv.org`
- `docs.github.com`
- `docs.python.org`
- `github.blog`
- `github.com`
- `realpython.com`

The templates are used only as network-read source-plan candidates and remain
dataflow-only. They do not perform external writes, do not enable real
execution, do not mutate production paths, and do not access production secrets.

Unsafe dork-style intent is rejected. Queries containing terms such as
credentials, secrets, tokens, password dumps, admin panels, exposed files,
private keys, dark web, or exploit-oriented terms are not generated.

---

### Safe public search template telemetry

Safe public search template telemetry reports how many allowlisted public search
template targets were seen, selected, fetched, and blocked by normal network-read
controls such as robots.txt, domain policy, or rate limits.

The runtime contract also verifies that unsafe public search templates remain at
zero.

Blocked safe templates are telemetry, not failures. They preserve the normal
network-read safety model and do not perform external writes, enable real
execution, mutate production paths, or access production secrets.

---

### Safe public search template ranking

Safe public search templates are ranked above generic public search targets but
below curated/direct evidence targets.

This keeps allowlisted public search discovery visible to the scheduler without
letting it displace higher-quality evidence URLs. The runtime contract remains
tolerant: safe templates must be seen and unsafe templates must remain zero, but
selection can vary by batch budget, robots.txt, and domain policy.

---

### Safe public search template audit

Explorer source planning emits a safe public search template audit summary.

The audit records:

- generated template count;
- accepted template count;
- rejected template count;
- unsafe rejected template count;
- deduped template count;
- template counts by allowlisted site;
- template counts by template kind;
- accepted query strings.

This is planning-time telemetry. It performs no external writes, does not enable
real execution, does not mutate production paths, and does not access production
secrets.

---

### Runtime/source-plan safe public search audit contract

The source-planned evidence runtime contract validates planning-time safe public
search audit telemetry together with node runtime telemetry.

The contract checks that safe public search audits remain dataflow-only and safe,
that accepted template counts are present when runtime search-template telemetry
is present, and that runtime unsafe template detections remain zero.

Robots.txt or domain-policy blocked safe templates remain valid telemetry and are
not contract failures.

---

### Memory vector-ready evidence schema

Memory evidence records and catalog query results include vector-ready schema
fields for future hybrid retrieval:

- `semantic_retrieval_enabled`
- `embedding_status`
- `embedding_model`
- `embedding_dim`
- `embedding_hash`
- `embedding_vector_ref`
- `embedding_updated_at`

This is schema-only. The runtime does not compute embeddings, does not connect to
a vector database, and does not enable semantic retrieval. Deterministic catalog
query remains the active retrieval path.

---

### Memory retrieval mode contract

Memory evidence catalog queries declare their retrieval mode explicitly.

Current retrieval mode is `deterministic`. Query results include deterministic
candidate telemetry and reserved semantic/hybrid retrieval fields:

- `retrieval_contract_version`
- `retrieval_mode`
- `hybrid_retrieval_enabled`
- `deterministic_candidates`
- `deterministic_candidate_count`
- `semantic_candidates`

Semantic and hybrid retrieval remain disabled. No embeddings are computed, no
vector database is queried, and deterministic catalog filtering/ranking remains
the active retrieval path.

---

### Memory evidence query contract checker

Memory evidence query JSON can be checked with:

```bash
python -m src.testing.check_memory_evidence_query_contract \
  /tmp/memory_query_result.json
```
The checker validates deterministic retrieval mode, vector-ready schema fields,
disabled hybrid/semantic retrieval, safety flags, result counts, and compact
deterministic candidate telemetry.

---

### Cluster CLI memory query contract smoke

The cluster CLI memory query command can write query JSON and validate the
memory evidence query contract in one smoke command:

```bash
python -m src.swarms.runtime.cluster_cli memory-query \
  --text-query "agents memory" \
  --limit 5 \
  --json \
  --json-output /tmp/memory_query_result.json \
  --check-contract
```
The contract check validates deterministic retrieval mode, disabled
semantic/hybrid retrieval, vector-ready schema fields, safety flags, result
counts, and deterministic candidate telemetry.

---

### Explorer-memory evidence replay query smoke

Explorer useful evidence memory records can be replayed into the memory evidence
catalog query contract with:

```bash
python -m src.testing.replay_explorer_memory_evidence_query \
  --text-query "agents memory" \
  --limit 5 \
  --json-output /tmp/explorer_memory_replay_query.json \
  --check-contract \
  --json
```
The replay smoke scans local JSON and/or CRDT sqlite payloads for
explorer_useful_evidence memory records, rebuilds the deterministic memory
evidence catalog, executes the catalog query, and validates the memory evidence
query contract.

This remains local-only and testing-only. It performs no external writes, does
not compute embeddings, does not query a vector database, and keeps semantic and
hybrid retrieval disabled.

---

### Cluster CLI explorer-memory replay query smoke

The cluster CLI can replay explorer useful evidence records into the memory
evidence query contract:

```bash
python -m src.swarms.runtime.cluster_cli memory-replay-query \
  --text-query "agents memory" \
  --limit 5 \
  --json \
  --json-output /tmp/explorer_memory_replay_query.json \
  --check-contract
```
The command wraps src.testing.replay_explorer_memory_evidence_query, scans local
CRDT sqlite and/or JSON input for explorer_useful_evidence memory records,
rebuilds the deterministic memory evidence catalog, and validates the memory
evidence query contract.

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

src/testing/run_guarded_repair_execution.py
src/testing/run_post_repair_evidence_check.py
src/testing/check_controlled_execution_readiness.py
src/testing/inspect_retry_governance_trail.py
src/swarms/security/runtime_validation.py
```
# Controlled Retry and Guarded Repair Runbook

This runbook documents the current verified controlled retry and guarded repair
execution milestone.

The goal is to provide an operator-friendly golden path from retry governance to
guarded repair execution and post-repair evidence verification.

The verified loop ends with:

```text
post_repair_status=passed
repair_outcome_verified=true
repair_targets_expected_count=9
repair_targets_verified_count=9
repair_targets_missing=[]
repair_targets_unexpected=[]
recommended_next_action=close_repair_loop
```

## Safety boundary

This milestone does not enable arbitrary real execution.

The current safety boundary is:

```text
real_execution_enabled=false
rendered_command_executed=false
dry_run_command_executed=false
```

The guarded repair execution harness may execute only the controlled repair
harness subprocess after approval, dry-run, noop, feedback, and readiness lineage
exist.

The post-repair evidence check may execute only the verification subprocess. It
must not perform additional repair execution:

```text
repair_execution_enabled=false
real_execution_enabled=false
repair_execution_performed=false
repair_subprocess_invoked=false
```

Any future arbitrary real execution adapter requires a separate policy-gated PR.

## Canonical smoke identifiers

The current canonical smoke chain uses:

```text
proposal_id=replay-retry-real-observe-smoke-1
rendered_command_id=replay-retry-real-observe-command-1
db_path=data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

## Runtime preflight

From the project root, compile the current verification helpers:

```bash
python -m py_compile \
  src/testing/run_guarded_repair_execution.py \
  src/testing/run_post_repair_evidence_check.py \
  src/testing/inspect_retry_governance_trail.py \
  src/testing/check_controlled_execution_readiness.py \
  src/swarms/security/runtime_validation.py
```

Run the focused unit tests:

```bash
python -m pytest -q \
  tests/unit/swarms/test_run_guarded_repair_execution.py \
  tests/unit/swarms/test_run_post_repair_evidence_check.py \
  tests/unit/swarms/test_check_controlled_execution_readiness.py \
  tests/unit/swarms/test_check_controlled_execution_readiness_schema.py \
  tests/unit/swarms/test_inspect_retry_governance_trail.py \
  tests/unit/security/test_directive_validation.py \
  tests/unit/swarms/test_experience_loop_docs.py
```

Run the broader smoke gates:

```bash
python -m pytest -q tests/unit/core tests/unit --maxfail=1
python -m src.testing.retry_governance_smoke \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
python -m src.testing.swarm_runtime_smoke
```

## Inspect the retry and repair trail

Use the governance trail inspector to verify that the chain is complete and that
the guarded repair and post-repair evidence artifacts are linked:

```bash
python -m src.testing.inspect_retry_governance_trail \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected high-level state:

```text
chain_complete=true
real_linkage_complete=true
real_dry_run_linkage_complete=true
real_noop_linkage_complete=true
real_read_only_promotion_linkage_complete=true
real_read_only_final_gate_linkage_complete=true
real_read_only_approval_linkage_complete=true
real_read_only_approval_transition_linkage_complete=true
real_read_only_readiness_gate_linkage_complete=true
real_read_only_execution_result_linkage_complete=true
real_read_only_feedback_linkage_complete=true
real_read_only_repair_plan_linkage_complete=true
real_read_only_repair_action_bundle_linkage_complete=true
real_read_only_repair_action_bundle_review_linkage_complete=true
real_repair_approval_linkage_complete=true
real_repair_approval_transition_linkage_complete=true
real_repair_final_gate_linkage_complete=true
real_repair_dry_run_envelope_linkage_complete=true
real_repair_noop_result_linkage_complete=true
real_repair_noop_feedback_linkage_complete=true
real_repair_readiness_gate_linkage_complete=true
guarded_repair_execution_linkage_complete=true
post_repair_evidence_linkage_complete=true
```

Expected guarded repair execution summary:

```text
guarded_repair_execution_statuses.succeeded=1
guarded_repair_execution_allowed.true=1
guarded_repair_execution_marker_observed.true=1
guarded_repair_execution_exit_codes.0=1
guarded_repair_execution_target_counts.9=1
guarded_repair_execution_next_actions.run_post_repair_evidence_check=1
guarded_repair_execution_repair_actions_executed.true=1
guarded_repair_execution_repair_execution_enabled.true=1
guarded_repair_execution_real_execution_enabled.false=1
guarded_repair_execution_rendered_command_executed.false=1
guarded_repair_execution_dry_run_command_executed.false=1
```

Expected post-repair evidence summary:

```text
post_repair_evidence_statuses.passed=1
post_repair_evidence_allowed.true=1
post_repair_evidence_enabled.true=1
post_repair_evidence_marker_observed.true=1
post_repair_evidence_exit_codes.0=1
post_repair_evidence_outcome_verified.true=1
post_repair_evidence_expected_counts.9=1
post_repair_evidence_verified_counts.9=1
post_repair_evidence_missing_counts.0=1
post_repair_evidence_unexpected_counts.0=1
post_repair_evidence_next_actions.close_repair_loop=1
post_repair_evidence_repair_execution_enabled.false=1
post_repair_evidence_real_execution_enabled.false=1
post_repair_evidence_repair_execution_performed.false=1
post_repair_evidence_repair_subprocess_invoked.false=1
```

## One-command golden-path smoke

After the full runtime chain exists, the final verification entrypoint is:

```bash
python -m src.testing.run_controlled_retry_guarded_repair_golden_path \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected result:

```text
type=controlled_retry_guarded_repair_golden_path_report
golden_path_status=passed
chain_complete=true
post_repair_status=passed
repair_outcome_verified=true
recommended_next_action=close_repair_loop
ready_for_real_execution=false
real_execution_enabled=false
failed_check_count=0
```

This command is verification-only. It reads the CRDT trail and does not publish
new records, run repair subprocesses, run evidence subprocesses, or enable real
execution.

## Check controlled execution readiness

The readiness report aggregates the chain, security validation, linkage, and
execution safety invariants:

```bash
python -m src.testing.check_controlled_execution_readiness \
  --proposal-id replay-retry-real-observe-smoke-1 \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --require-operator-authorized \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected final state includes:

```text
status=passed
ready_for_mock_execution=true
ready_for_real_execution=false
real_execution_not_supported_yet
guarded_repair_execution_observed=true
guarded_repair_execution_succeeded=1
guarded_repair_execution_allowed=1
guarded_repair_execution_repair_actions_executed=1
guarded_repair_execution_real_execution_enabled=0
post_repair_evidence_observed=true
post_repair_evidence_passed=1
post_repair_evidence_outcome_verified=1
post_repair_evidence_next_action_close_loop=1
post_repair_evidence_repair_execution_enabled=0
post_repair_evidence_real_execution_enabled=0
```

## Run guarded repair execution

Run this only after the repair readiness gate is present and surfaced.

The allowed runtime command is:

```bash
python -m src.testing.run_guarded_repair_execution \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --allow-guarded-repair-execution \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected result:

```text
type=replay_lifecycle_retry_guarded_repair_execution_result
repair_execution_status=succeeded
repair_execution_allowed=true
guarded_repair_execution=true
guarded_repair_marker_observed=true
exit_code=0
repair_action_target_count=9
repair_actions_executed=true
repair_bundle_executed=true
repair_command_executed=true
rendered_command_executed=false
dry_run_command_executed=false
repair_execution_enabled=true
real_execution_enabled=false
repair_execution_performed=true
repair_subprocess_invoked=true
recommended_next_action=run_post_repair_evidence_check
```

Fail-closed behavior:

```bash
python -m src.testing.run_guarded_repair_execution \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Without `--allow-guarded-repair-execution`, the runner must publish or return a
rejected non-executing result instead of performing the guarded repair harness.

## Run post-repair evidence verification

Run this only after a succeeded guarded repair execution result exists.

The allowed runtime command is:

```bash
python -m src.testing.run_post_repair_evidence_check \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --allow-post-repair-evidence-check \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Expected result:

```text
type=replay_lifecycle_retry_post_repair_evidence_check
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
repair_execution_enabled=false
real_execution_enabled=false
repair_execution_performed=false
repair_subprocess_invoked=false
recommended_next_action=close_repair_loop
```

Fail-closed behavior:

```bash
python -m src.testing.run_post_repair_evidence_check \
  --rendered-command-id replay-retry-real-observe-command-1 \
  --json \
  --db-path data/cluster_runtime/latest/ledgers/swarm_crdt.local.db
```

Without `--allow-post-repair-evidence-check`, the runner must publish or return a
rejected non-verifying result instead of running the evidence verification
subprocess.

## Golden-path checklist

A verified controlled retry and guarded repair loop requires all of the following:

```text
[ ] retry governance trail complete
[ ] controlled execution result observed
[ ] real preflight blocked
[ ] real approval transition approved
[ ] real final gate blocked
[ ] real dry-run envelope linked
[ ] real noop result linked
[ ] read-only promotion linked
[ ] read-only final gate linked
[ ] read-only approval transition approved
[ ] read-only readiness gate ready_blocked
[ ] guarded read-only execution result observed
[ ] read-only feedback actionable
[ ] repair plan planned
[ ] repair action bundle assembled
[ ] repair action bundle review approved
[ ] repair approval transition approved
[ ] repair final gate ready_blocked
[ ] repair dry-run envelope prepared
[ ] repair noop result completed
[ ] repair noop feedback actionable
[ ] repair readiness gate ready_blocked
[ ] guarded repair execution succeeded
[ ] post-repair evidence check passed
[ ] post-repair evidence recommends close_repair_loop
```

## Final milestone definition

The milestone is complete when the runtime can show:

```text
guarded_repair_execution_statuses.succeeded=1
post_repair_evidence_statuses.passed=1
repair_outcome_verified=true
repair_targets_verified_count=9
post_repair_evidence_orphans=0
ready_for_real_execution=false
real_execution_enabled=false
recommended_next_action=close_repair_loop
```

At this point BlackSwan has a verified, auditable, fail-closed repair loop from
retry governance to post-repair evidence.

## Next milestones

```text
PR 37.1 — final golden-path smoke script
PR 37.2 — docs/schema/test fixture cleanup
PR 38.x — policy-gated real execution adapter scaffold
```

Real execution remains out of scope until PR 38.x or later.

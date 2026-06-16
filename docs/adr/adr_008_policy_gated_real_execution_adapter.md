# ADR-008: Policy-Gated Real Execution Adapter

## Status

Accepted for design.

Implementation is intentionally deferred to later PRs.

This ADR does not enable arbitrary real execution.

## Context

BlackSwan now has a verified controlled retry and guarded repair lifecycle.

The current verified loop can move from failed read-only evidence to actionable
feedback, reviewed repair planning, repair approval, guarded repair execution,
post-repair evidence verification, and `close_repair_loop`.

The verified milestone includes:

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

This proves the runtime can coordinate, audit, repair, and verify a guarded
execution path.

However, arbitrary real execution remains disabled. The current guarded repair
harness does not execute the original rendered command, does not execute the
dry-run command, and does not enable unrestricted external side effects.

The next architectural step is to define how a future real execution adapter
could exist without weakening the current safety guarantees.

## Decision

BlackSwan will introduce real execution only through a policy-gated adapter
contract.

The adapter must be:

* fail-closed by default,
* disabled unless explicitly enabled by policy,
* capability-scoped,
* sandbox-first,
* audit-first,
* approval-gated,
* rollback-aware,
* linked to existing CRDT governance records,
* visible through Security, Inspector, Readiness, and Overseer summaries,
* verified by post-execution evidence checks.

No direct command execution path may bypass this adapter contract.

No swarm may execute arbitrary shell commands by directly consuming a rendered
command string.

## Execution levels

The platform recognizes the following execution levels:

```text
advisory
dry-run
noop
guarded-read-only
guarded-repair
sandbox-real
policy-gated-real
```

### advisory

Produces recommendations, briefs, proposals, or plans.

No subprocess execution.

### dry-run

Builds command envelopes or validates intent.

No real external side effects.

### noop

Runs a controlled noop subprocess to prove scheduling, linkage, and marker
observation.

No original command execution.

### guarded-read-only

Runs an explicitly controlled read-only harness.

May inspect or verify state.

Must not mutate external state.

### guarded-repair

Runs an explicitly controlled repair harness after approval and readiness
lineage.

Must not execute arbitrary rendered commands.

Must not enable unrestricted real execution.

### sandbox-real

Future execution level.

May execute scoped actions only inside an ephemeral sandbox workspace.

May not write to production paths.

May not access production secrets.

May not perform network or external side effects unless explicitly allowed by
policy.

Must produce post-execution evidence.

### policy-gated-real

Future execution level.

May perform real side effects only after policy authorization, capability
validation, approval lineage, final gate, dry-run envelope, rollback plan, and
post-execution verification.

This level is out of scope until a later reviewed milestone.

## Adapter contract

A future real execution adapter must consume an explicit adapter request record.

The request must include:

```text
adapter_request_id
proposal_id
rendered_command_id
capability_id
execution_level
policy_id
approval_id
approval_transition_id
final_gate_id
dry_run_envelope_id
operator_authorized
sandbox_required
rollback_required
post_execution_evidence_required
```

The adapter must emit an immutable result record with:

```text
adapter_result_id
adapter_request_id
execution_status
execution_level
capability_id
policy_id
sandbox_id
exit_code
stdout_digest
stderr_digest
duration_seconds
execution_performed
subprocess_invoked
real_execution_enabled
external_side_effects_performed
rollback_plan_id
rollback_performed
post_execution_evidence_id
recommended_next_action
```

The adapter result must never rely only on logs. It must be published into CRDT
as a first-class audit record.

## Required gates

A real execution adapter request is valid only when all required gates are true.

Required gates:

```text
operator_authorized=true
policy_authorized=true
capability_allowed=true
approval_transition_status=approved
final_gate_status=ready
dry_run_envelope_ready=true
rollback_plan_present=true
post_execution_evidence_required=true
security_validation_passed=true
readiness_validation_passed=true
```

If any gate is missing, false, unknown, stale, orphaned, or invalid, the adapter
must publish a rejected result and perform no execution.

## Capability model

Capabilities are named, versioned, and explicitly scoped.

A capability must define:

```text
capability_id
capability_version
execution_level
allowed_modules
allowed_paths
allowed_arguments
allowed_environment_keys
network_policy
secret_policy
filesystem_policy
timeout_policy
resource_limits
rollback_strategy
evidence_strategy
```

Capabilities must be deny-by-default.

Unknown capabilities are rejected.

Capabilities cannot be inferred from command strings.

## Policy model

Policies decide whether a capability may run in a given context.

A policy must evaluate:

```text
proposal_id
swarm_id
operator_authorized
approval_lineage
risk_level
execution_level
capability_id
target_paths
target_modules
resource_limits
sandbox_required
rollback_required
post_execution_evidence_required
```

A policy decision must be materialized as a CRDT record.

Allowed decision statuses:

```text
approved
rejected
blocked
expired
superseded
```

Only `approved` can continue.

All other statuses must fail closed.

## Sandbox-first rule

The first implementation of real execution must target sandbox execution only.

Sandbox execution must:

* create an isolated temporary workspace,
* copy only explicitly allowed inputs,
* deny production secret access,
* deny production path writes,
* apply repair/action bundles only inside the sandbox,
* run verification inside the sandbox,
* publish evidence,
* destroy or archive the sandbox according to policy.

Sandbox execution must not mutate the live repository or runtime state unless a
later policy-gated milestone explicitly allows it.

## Rollback and compensation

Every policy-gated real execution request must have a rollback or compensation
story before execution.

For sandbox execution, rollback can be workspace destruction.

For future production-affecting execution, rollback must be explicit and
validated before execution.

Missing rollback plan means:

```text
execution_status=rejected
execution_performed=false
subprocess_invoked=false
recommended_next_action=prepare_rollback_plan
```

## Evidence requirements

Every execution result must be followed by post-execution evidence.

Evidence must verify:

```text
expected_targets
actual_targets
missing_targets
unexpected_targets
exit_code
marker_observed
policy_id
capability_id
sandbox_id
side_effects
rollback_status
```

A completed execution without evidence is not considered successful.

## Security invariants

The adapter must preserve these invariants:

```text
unknown_policy_rejected=true
unknown_capability_rejected=true
missing_approval_rejected=true
missing_final_gate_rejected=true
missing_dry_run_envelope_rejected=true
missing_rollback_plan_rejected=true
missing_post_execution_evidence_rejected=true
orphaned_records_rejected=true
stale_records_rejected=true
```

For non-real modes, the current invariants remain:

```text
ready_for_real_execution=false
real_execution_enabled=false
```

For sandbox-real mode, the adapter may set:

```text
sandbox_execution_enabled=true
```

but must still keep:

```text
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```

For future policy-gated-real mode, any external side effect must be explicitly
authorized, scoped, audited, and verified.

## Observability requirements

Security validation must validate every adapter request and result.

The inspector must summarize:

```text
adapter_request_records
adapter_result_records
adapter_statuses
adapter_policy_decisions
adapter_capabilities
adapter_execution_levels
adapter_sandbox_ids
adapter_exit_codes
adapter_orphans
adapter_linkage_complete
external_side_effects_performed
production_paths_mutated
post_execution_evidence_linkage_complete
```

Readiness must fail if:

```text
adapter_linkage_complete=false
adapter_orphans>0
unknown_capability_detected=true
unknown_policy_detected=true
missing_rollback_plan=true
missing_post_execution_evidence=true
external_side_effects_performed=true without policy approval
```

Overseer summaries must surface adapter status, policy decisions, blocked
reasons, sandbox evidence, and post-execution verification.

## Non-goals

This ADR does not implement:

* arbitrary real execution,
* production side effects,
* autonomous code-changing execution,
* unrestricted shell access,
* network-enabled execution,
* secret access,
* multi-proposal batch repair execution,
* live repository mutation,
* production policy scheduler.

## Implementation sequence

Future PRs should proceed in this order:

```text
PR 38.1 — real execution adapter contract and schemas, still not runnable
PR 38.2 — sandbox-only adapter scaffold, fail-closed by default
PR 38.3 — capability registry and policy matrix
PR 38.4 — sandbox evidence and rollback records
PR 38.5 — sandbox repair action application, no production mutation
PR 38.6 — surface sandbox adapter in Security/Inspector/Readiness
PR 38.7 — golden-path sandbox execution smoke
PR 39.x — reviewed policy-gated real execution design
```

## Acceptance criteria for PR 38.1

PR 38.1 may be accepted only if:

```text
real_execution_adapter_contract_exists=true
adapter_request_schema_exists=true
adapter_result_schema_exists=true
unknown_capability_rejected=true
unknown_policy_rejected=true
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
```

The concrete PR 38.1 artifact is:

```text
replay_lifecycle_retry_real_execution_adapter_contract
```

It is a contract/schema record only. It is valid after a passed post-repair
evidence check and must keep:

```text
adapter_contract_exists=true
adapter_request_schema_exists=true
adapter_result_schema_exists=true
unknown_capability_rejected=true
unknown_policy_rejected=true
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
```

## Acceptance criteria for PR 38.3a

The concrete PR 38.3a artifact is:

```text
replay_lifecycle_retry_real_execution_adapter_request_schema
```
It is a schema/scaffold record only. It is valid after a defined
replay_lifecycle_retry_real_execution_adapter_contract and must keep:
```text
adapter_request_schema_status=defined
adapter_request_schema_exists=true
request_generation_enabled=false
request_execution_enabled=false
adapter_implementation_enabled=false
adapter_result_generation_enabled=false
sandbox_execution_enabled=false
policy_gated_real_execution_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
recommended_next_action=prepare_capability_registry_and_policy_matrix
```

## Acceptance criteria for PR 38.4a

The concrete PR 38.4a artifact is:

```text
replay_lifecycle_retry_real_execution_capability_policy_matrix
```

It defines the initial capability registry and policy matrix for future adapter
request generation.

It is still not runnable and must keep:
```text
capability_registry_exists=true
policy_matrix_exists=true
capability_count=7
enabled_capability_count=5
blocked_capability_count=2
policy_rule_count=7
approved_policy_count=5
blocked_policy_count=2
unknown_capability_rejected=true
unknown_policy_rejected=true
deny_by_default=true
fail_closed_default=true
sandbox_real_blocked=true
policy_gated_real_blocked=true
external_side_effects_allowed=false
production_paths_allowed=false
production_secrets_allowed=false
capability_execution_enabled=false
policy_execution_enabled=false
adapter_request_generation_enabled=false
adapter_request_execution_enabled=false
adapter_result_generation_enabled=false
sandbox_execution_enabled=false
policy_gated_real_execution_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
recommended_next_action=prepare_sandbox_adapter_scaffold
```

## Acceptance criteria for PR 38.5a

The concrete PR 38.5a artifact is:

```text
replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold
```
It defines a fail-closed sandbox adapter scaffold after the capability registry
and policy matrix exist.

It is still not runnable and must keep:
```text
sandbox_adapter_scaffold_status=defined
sandbox_adapter_scaffold_exists=true
sandbox_adapter_contract_exists=true
sandbox_workspace_strategy=ephemeral_temp_workspace
sandbox_input_strategy=explicit_allowlist_only
sandbox_output_strategy=explicit_allowlist_only
sandbox_rollback_strategy=workspace_destruction
sandbox_evidence_strategy=post_execution_evidence_required
sandbox_network_policy=deny
sandbox_secret_policy=deny
sandbox_filesystem_policy=no_production_writes
sandbox_production_write_policy=deny
sandbox_external_side_effect_policy=deny
sandbox_adapter_fail_closed=true
sandbox_adapter_deny_by_default=true
sandbox_adapter_requires_policy_matrix=true
sandbox_adapter_requires_known_capability=true
sandbox_adapter_requires_known_policy=true
sandbox_adapter_requires_operator_authorization=true
sandbox_adapter_requires_approval_lineage=true
sandbox_adapter_requires_final_gate=true
sandbox_adapter_requires_dry_run_envelope=true
sandbox_adapter_requires_rollback_plan=true
sandbox_adapter_requires_post_execution_evidence=true
sandbox_adapter_rejects_unknown_capability=true
sandbox_adapter_rejects_unknown_policy=true
sandbox_adapter_implementation_enabled=false
sandbox_workspace_creation_enabled=false
sandbox_input_materialization_enabled=false
sandbox_command_rendering_enabled=false
sandbox_execution_enabled=false
sandbox_result_generation_enabled=false
adapter_request_generation_enabled=false
adapter_request_execution_enabled=false
adapter_result_generation_enabled=false
capability_execution_enabled=false
policy_execution_enabled=false
policy_gated_real_execution_enabled=false
execution_performed=false
subprocess_invoked=false
real_execution_enabled=false
external_side_effects_performed=false
production_paths_mutated=false
production_secrets_accessed=false
recommended_next_action=surface_sandbox_adapter_scaffold_observability
```

## Acceptance criteria for PR 38.5c

PR 38.5c surfaces sandbox adapter scaffold observability through a dedicated
read-only check and Overseer brief metrics.

The concrete helper is:

```text
src.testing.check_sandbox_adapter_scaffold_observability
```
It must verify:
```text
sandbox_adapter_scaffold_observed=true
sandbox_adapter_scaffold_linkage_complete=true
sandbox_adapter_scaffold_orphans=0
sandbox_adapter_scaffold_defined=1
sandbox_adapter_scaffold_fail_closed=1
sandbox_adapter_scaffold_deny_by_default=1
sandbox_adapter_scaffold_sandbox_execution_enabled=0
sandbox_adapter_scaffold_execution_performed=0
sandbox_adapter_scaffold_subprocess_invoked=0
sandbox_adapter_scaffold_real_execution_enabled=0
sandbox_adapter_scaffold_external_side_effects_performed=0
sandbox_adapter_scaffold_production_paths_mutated=0
sandbox_adapter_scaffold_production_secrets_accessed=0
```

The Overseer brief must surface the same fail-closed scaffold state through
security_real_execution_sandbox_adapter_scaffold_* key metrics.

This PR remains read-only and does not enable sandbox execution.

## Acceptance criteria for PR 38.6a

PR 38.6a introduces a fail-closed sandbox adapter request preflight scaffold.

The concrete builder is:

```text
src.testing.build_real_execution_sandbox_adapter_request_preflight
```
It may only build records from a valid
replay_lifecycle_retry_real_execution_sandbox_adapter_scaffold source.

The produced record type is:

```text
replay_lifecycle_retry_real_execution_sandbox_adapter_request_preflight
```

Required invariants:
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

This PR does not enable sandbox execution. It only prepares the next blocked
preflight artifact.

## Acceptance criteria for PR 38.6c

PR 38.6c surfaces sandbox adapter request preflight observability through a
dedicated read-only check and Overseer brief metrics.

The concrete helper is:

```text
src.testing.check_sandbox_adapter_request_preflight_observability
```
It must verify:
```text
sandbox_adapter_request_preflight_observed=true
sandbox_adapter_request_preflight_linkage_complete=true
sandbox_adapter_request_preflight_orphans=0
sandbox_adapter_request_preflight_blocked=1
sandbox_adapter_request_preflight_fail_closed=1
sandbox_adapter_request_preflight_deny_by_default=1
sandbox_adapter_request_preflight_request_generation_enabled=0
sandbox_adapter_request_preflight_workspace_creation_enabled=0
sandbox_adapter_request_preflight_input_materialization_enabled=0
sandbox_adapter_request_preflight_command_rendering_enabled=0
sandbox_adapter_request_preflight_sandbox_execution_enabled=0
sandbox_adapter_request_preflight_result_generation_enabled=0
sandbox_adapter_request_preflight_execution_performed=0
sandbox_adapter_request_preflight_subprocess_invoked=0
sandbox_adapter_request_preflight_real_execution_enabled=0
sandbox_adapter_request_preflight_external_side_effects_performed=0
sandbox_adapter_request_preflight_production_paths_mutated=0
sandbox_adapter_request_preflight_production_secrets_accessed=0
```
The Overseer brief must surface the same fail-closed request preflight state
through security_real_execution_sandbox_adapter_request_preflight_* key
metrics.

This PR remains read-only and does not enable sandbox request generation,
workspace creation, input materialization, command rendering, sandbox execution,
subprocesses, or real execution.

## Consequences

This decision keeps BlackSwan aligned with the existing audit-first architecture.

It allows the project to move toward real execution without introducing a direct
shell-command path or bypassing policy, approval, readiness, rollback, and
evidence gates.

The cost is more ceremony before execution. This is intentional. The platform is
designed for controlled autonomy, not uncontrolled automation.

## Summary

BlackSwan may eventually support real execution, but only through a
policy-gated, capability-scoped, sandbox-first, rollback-aware, evidence-verified
adapter contract. policy-gated adapter contract.

Until that adapter is implemented and reviewed, arbitrary real execution remains
disabled.

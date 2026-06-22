# Cluster Latest Artifacts Lifecycle

This runbook describes the local latest-artifacts lifecycle used by the
Explorer → Memory replay smoke and cluster runtime artifact inspection tools.

The lifecycle is intentionally operator-facing, contract-checked, and local by
default. It does not enable semantic retrieval, hybrid retrieval, external
writes, production path mutation, production secret access, or arbitrary real
execution.

## Lifecycle overview

```text
memory-replay-smoke
  -> write latest artifact
  -> inspect latest memory replay artifact
  -> index latest artifacts
  -> inspect retention
  -> cleanup dry-run
  -> optional execute-local-artifacts gate
  -> post-cleanup verification
```

The canonical latest artifacts directory is:

```text
data/cluster_runtime/latest/artifacts/
```

The current Explorer → Memory replay smoke artifact is:

```text
data/cluster_runtime/latest/artifacts/explorer_memory_replay_smoke.json
```

## 1. Generate and persist the Explorer → Memory replay smoke artifact

Run the one-command Explorer runtime + Memory replay contract smoke:

```bash
python -m src.swarms.runtime.cluster_cli memory-replay-smoke \
  --goal "autonomous agents memory systems" \
  --ticks 3 \
  --json \
  --write-latest \
  --check-contract
```

Expected confirmations:

```text
✅ explorer source-planned evidence loop contract OK
✅ memory evidence query contract OK
✅ explorer memory replay smoke OK
✅ explorer memory replay smoke contract OK
```

Expected high-level result shape:

```json
{
  "type": "explorer_memory_replay_smoke_result",
  "status": "passed",
  "latest_artifact_path": "data/cluster_runtime/latest/artifacts/explorer_memory_replay_smoke.json",
  "retrieval_mode": "deterministic",
  "semantic_retrieval_enabled": false,
  "hybrid_retrieval_enabled": false,
  "memory_replay_summary": {
    "status": "passed",
    "records_published": 7,
    "artifact_records": 7,
    "records_replayed": 7,
    "query_results": 5,
    "artifact_capture_ratio": 1.0,
    "replay_acceptance_ratio": 1.0,
    "full_replay_path_ratio": 0.7143
  }
}
```

## 2. Inspect the latest memory replay artifact

After `--write-latest`, inspect the latest memory replay artifact without
passing an explicit path:

```bash
python -m src.swarms.runtime.cluster_cli memory-replay-latest \
  --json \
  --check-contract
```

Expected confirmation:

```text
✅ latest memory replay smoke artifact contract OK
```

This command is read-only. It validates the latest smoke artifact and prints the
compact `memory_replay_summary` plus detailed `memory_replay_yield` metrics.

## 3. Index all latest artifacts

Inspect all latest runtime artifacts under `data/cluster_runtime/latest/artifacts/`:

```bash
python -m src.swarms.runtime.cluster_cli latest-artifacts \
  --json \
  --check-contract
```

Expected confirmation:

```text
✅ cluster latest artifacts contract OK
```

Expected high-level result shape:

```json
{
  "type": "cluster_latest_artifacts_summary",
  "status": "indexed",
  "artifact_count": 1,
  "known_artifact_count": 1,
  "invalid_artifact_count": 0,
  "contract_ok": true,
  "artifacts": [
    {
      "name": "explorer_memory_replay_smoke",
      "type": "explorer_memory_replay_smoke_result",
      "status": "passed",
      "contract_checked": true,
      "contract_ok": true
    }
  ]
}
```

Unknown artifact types are included in the index, but they are marked
contract-invalid so they do not silently pass operator or CI checks.

## 4. Inspect retention policy

The latest-artifacts index can report inspect-only retention metrics:

```bash
python -m src.swarms.runtime.cluster_cli latest-artifacts \
  --json \
  --check-contract \
  --retention-max-age-days 7
```

Expected retention shape:

```json
{
  "stale_artifact_count": 0,
  "invalid_artifact_count": 0,
  "retention": {
    "mode": "inspect_only",
    "max_age_seconds": 604800.0,
    "max_age_days": 7.0,
    "would_delete_count": 0,
    "would_delete": []
  }
}
```

Retention inspection never deletes files.

## 5. Run cleanup dry-run

Dry-run cleanup reports which local latest artifacts would be deleted, without
deleting anything:

```bash
python -m src.swarms.runtime.cluster_cli latest-artifacts-cleanup \
  --retention-max-age-days 7 \
  --dry-run \
  --json \
  --check-contract
```

Expected confirmation:

```text
✅ cluster latest artifacts cleanup dry-run contract OK
```

Expected dry-run safety shape:

```json
{
  "type": "cluster_latest_artifacts_cleanup_result",
  "mode": "dry_run",
  "deleted_count": 0,
  "deleted": [],
  "local_artifact_deletion_performed": false,
  "external_write_performed": false,
  "real_execution_enabled": false,
  "production_paths_mutated": false,
  "production_secrets_accessed": false
}
```

## 6. Execute local cleanup gate

Actual deletion is available only through an explicit local gate:

```bash
python -m src.swarms.runtime.cluster_cli latest-artifacts-cleanup \
  --retention-max-age-days 7 \
  --execute-delete-local-artifacts \
  --json \
  --check-contract
```

Execution mode deletes only files that are already listed in
`retention.would_delete`, only when the artifacts root is the allowlisted local
latest artifacts directory, and only for regular files inside that root.

Allowed root:

```text
data/cluster_runtime/latest/artifacts/
```

The execute result reports:

```json
{
  "mode": "execute_delete_local_artifacts",
  "artifacts_root_allowed": true,
  "execute_delete_local_artifacts": true,
  "local_artifact_deletion_performed": true,
  "deleted_count": 1,
  "deleted": [],
  "deletion_errors": []
}
```

If the artifacts root is not allowlisted, execute mode is blocked and no files
are deleted.

## 7. Verify post-cleanup summary

Cleanup results include `post_cleanup`, which verifies the latest artifacts
state after the cleanup operation.

For dry-run, this is a read-only verification of the current index.

For execute mode, this is a fresh read-only reindex after deletion.

```json
{
  "post_cleanup": {
    "checked": true,
    "status": "indexed",
    "artifact_count": 1,
    "known_artifact_count": 1,
    "invalid_artifact_count": 0,
    "stale_artifact_count": 0,
    "cleanup_ok": true,
    "retention": {
      "mode": "inspect_only",
      "would_delete_count": 0
    }
  }
}
```

Dry-run may report `cleanup_ok=false` when stale artifacts exist, because dry-run
does not delete files. Execute mode requires stale and would-delete counts to be
zero after successful cleanup.

## Safety guarantees

The latest-artifacts lifecycle is local and operator-facing.

The smoke and artifact inspection path keeps:

```text
external_write_performed=false
real_execution_enabled=false
production_paths_mutated=false
production_secrets_accessed=false
semantic_retrieval_enabled=false
hybrid_retrieval_enabled=false
```

Cleanup dry-run keeps:

```text
deleted_count=0
deleted=[]
local_artifact_deletion_performed=false
```

Execute cleanup may set:

```text
local_artifact_deletion_performed=true
```

only when `--execute-delete-local-artifacts` is passed and the target files are
allowlisted local latest artifacts. This local artifact deletion is not an
external write, not arbitrary real execution, not production path mutation, and
not production secret access.

## Operator checklist

Use this checklist after changing Explorer → Memory replay or latest-artifact
contracts.

1. Run the full unit suite:

```bash
python -m pytest -q tests/unit/core tests/unit --maxfail=1
```

2. Run runtime smoke:

```bash
python -m src.testing.swarm_runtime_smoke
```

3. Generate and persist the latest memory replay smoke artifact:

```bash
python -m src.swarms.runtime.cluster_cli memory-replay-smoke \
  --goal "autonomous agents memory systems" \
  --ticks 3 \
  --json \
  --write-latest \
  --check-contract
```

4. Inspect the latest memory replay artifact:

```bash
python -m src.swarms.runtime.cluster_cli memory-replay-latest \
  --json \
  --check-contract
```

5. Index latest artifacts:

```bash
python -m src.swarms.runtime.cluster_cli latest-artifacts \
  --json \
  --check-contract \
  --retention-max-age-days 7
```

6. Run cleanup dry-run:

```bash
python -m src.swarms.runtime.cluster_cli latest-artifacts-cleanup \
  --retention-max-age-days 7 \
  --dry-run \
  --json \
  --check-contract
```

7. Use execute cleanup only when stale local artifacts should actually be
   removed:

```bash
python -m src.swarms.runtime.cluster_cli latest-artifacts-cleanup \
  --retention-max-age-days 7 \
  --execute-delete-local-artifacts \
  --json \
  --check-contract
```

8. Confirm post-cleanup verification:

```text
post_cleanup.checked=true
post_cleanup.invalid_artifact_count=0
post_cleanup.stale_artifact_count=0
post_cleanup.retention.would_delete_count=0
```

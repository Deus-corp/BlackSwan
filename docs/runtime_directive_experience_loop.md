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

## Next steps

Planned follow-up work:

1. Memory swarm consumes `runtime_evidence` memory records.
2. Overseer links evidence records back into briefs.
3. Security validates directives and directive results.
4. Dashboard shows briefs, directives, results, evidence, and memory records.
5. Simulation can replay verified runtime evidence as scenarios.

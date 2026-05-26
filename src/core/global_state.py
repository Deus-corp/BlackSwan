"""Canonical global state snapshot for recovery, synchronization, and decisions."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
    )


class GlobalState:
    """Canonical source of truth for system-wide state."""

    __slots__ = ("state", "_snapshot_cid")

    REQUIRED_SECTIONS: tuple[str, ...] = (
        "knowledge_graph",
        "economic_state",
        "infrastructure_state",
        "execution_state",
        "security_state",
        "component_status",
    )

    def __init__(self, initial_state: dict[str, Any] | None = None) -> None:
        if initial_state is not None and not isinstance(initial_state, dict):
            raise TypeError("initial_state must be a dictionary or None")

        self.state: dict[str, Any] = (
            self.default_state()
            if initial_state is None
            else self._merge_defaults(initial_state)
        )
        self._snapshot_cid: str | None = None

    @staticmethod
    def default_state() -> dict[str, Any]:
        return {
            "version": "2.0",
            "timestamp": _utc_now_iso(),
            "knowledge_graph": {
                "crdt_root": "",
                "l2_snapshot": "",
                "l3_invariants": [],
            },
            "economic_state": {
                "treasury_balance": {"USDC": 0.0, "ETH": 0.0},
                "active_positions": [],
                "capital_allocation": {
                    "operational": 0.4,
                    "reserve": 0.3,
                    "active_growth": 0.3,
                },
                "genomes": {},
            },
            "infrastructure_state": {
                "core_nodes": [],
                "edge_nodes": [],
                "physical_sites": [],
            },
            "execution_state": {
                "active_tasks": [],
                "sandbox_pool": [],
            },
            "security_state": {
                "incident_log": [],
                "active_threat_level": "low",
                "last_audit_timestamp": "",
            },
            "component_status": {
                "curiosity_engine": "dormant",
                "social_modeling_engine": "dormant",
                "value_drift_detector": "dormant",
                "stigmergy_engine": "active",
                "counter_stigmergy_detector": "active",
            },
        }

    @classmethod
    def _merge_defaults(cls, initial_state: dict[str, Any]) -> dict[str, Any]:
        merged = cls.default_state()
        for key, value in initial_state.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(copy.deepcopy(value))
            else:
                merged[key] = copy.deepcopy(value)

        merged.setdefault("timestamp", _utc_now_iso())
        merged.setdefault("version", "2.0")
        return merged

    def __repr__(self) -> str:
        version = self.state.get("version", "unknown")
        timestamp = self.state.get("timestamp", "N/A")
        snapshot_cid = f"{self._snapshot_cid[:8]}..." if self._snapshot_cid else "None"
        return f"GlobalState(v={version}, ts={timestamp}, cid_prefix={snapshot_cid})"

    def snapshot(self) -> str:
        """Return a deterministic SHA-256 snapshot CID for the current state."""
        self._snapshot_cid = hashlib.sha256(
            _canonical_json(self.state).encode("utf-8")
        ).hexdigest()
        return self._snapshot_cid

    def restore(self, cid: str) -> None:
        clean_cid = str(cid or "").strip()
        if not clean_cid:
            raise ValueError("cid must be a non-empty string")
        raise NotImplementedError("IPFS integration not yet implemented for GlobalState restore.")

    def update(self, component: str, delta: dict[str, Any] | list[Any] | Any) -> None:
        """Apply a top-level state update and refresh timestamp."""
        clean_component = str(component or "").strip()
        if not clean_component:
            raise ValueError("component must be a non-empty string")

        if clean_component in self.state:
            current = self.state[clean_component]

            if isinstance(current, dict) and isinstance(delta, dict):
                current.update(copy.deepcopy(delta))
            elif isinstance(current, list):
                if isinstance(delta, list):
                    self.state[clean_component] = copy.deepcopy(delta)
                else:
                    current.append(copy.deepcopy(delta))
            else:
                self.state[clean_component] = copy.deepcopy(delta)
        else:
            self.state[clean_component] = copy.deepcopy(delta)

        self.touch()

    def set_path(self, path: str, value: Any) -> None:
        """Set a nested state value using dot-separated path syntax."""
        parts = [part.strip() for part in str(path or "").split(".") if part.strip()]
        if not parts:
            raise ValueError("path must be a non-empty dot-separated string")

        target = self.state
        for part in parts[:-1]:
            next_value = target.setdefault(part, {})
            if not isinstance(next_value, dict):
                next_value = {}
                target[part] = next_value
            target = next_value

        target[parts[-1]] = copy.deepcopy(value)
        self.touch()

    def get_path(self, path: str, default: Any = None) -> Any:
        """Get a nested state value using dot-separated path syntax."""
        parts = [part.strip() for part in str(path or "").split(".") if part.strip()]
        if not parts:
            return default

        current: Any = self.state
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]

        return copy.deepcopy(current)

    def touch(self) -> None:
        """Update the state timestamp and invalidate cached CID."""
        self.state["timestamp"] = _utc_now_iso()
        self._snapshot_cid = None

    def verify_invariants(self) -> list[str]:
        """Return a list of state invariant violations."""
        violations: list[str] = []

        for section in self.REQUIRED_SECTIONS:
            if section not in self.state:
                violations.append(f"Missing section: {section}")

        economic_state = self.state.get("economic_state", {})
        if not isinstance(economic_state, dict):
            violations.append("Invalid section: economic_state must be a dictionary")
            economic_state = {}

        capital_allocation = economic_state.get("capital_allocation", {})
        if isinstance(capital_allocation, dict):
            for key, value in capital_allocation.items():
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    violations.append(f"Economic invariant violation: allocation {key!r} is not numeric")
                    continue

                if numeric < 0:
                    violations.append(
                        f"Economic invariant violation: Negative {key} allocation ({numeric})"
                    )
        else:
            violations.append("Economic invariant violation: capital_allocation must be a dictionary")

        treasury = economic_state.get("treasury_balance", {})
        if isinstance(treasury, dict):
            for asset, value in treasury.items():
                try:
                    balance = float(value)
                except (TypeError, ValueError):
                    violations.append(f"Economic invariant violation: treasury {asset!r} is not numeric")
                    continue

                if balance < 0:
                    violations.append(
                        f"Economic invariant violation: Negative treasury balance {asset}={balance}"
                    )

        security_state = self.state.get("security_state", {})
        if isinstance(security_state, dict):
            last_audit_timestamp = security_state.get("last_audit_timestamp")
            if last_audit_timestamp:
                if not isinstance(last_audit_timestamp, str):
                    violations.append(
                        "Security invariant violation: 'last_audit_timestamp' is not a string"
                    )
                else:
                    try:
                        datetime.fromisoformat(last_audit_timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        violations.append(
                            "Security invariant violation: "
                            f"'last_audit_timestamp' is not valid ISO format: {last_audit_timestamp}"
                        )
        else:
            violations.append("Invalid section: security_state must be a dictionary")

        return violations

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def to_json(self) -> str:
        return json.dumps(
            self.state,
            indent=2,
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, json_str: str) -> GlobalState:
        state = json.loads(json_str)
        if not isinstance(state, dict):
            raise TypeError("Decoded JSON must be a dictionary")
        return cls(initial_state=state)

    def save_genome(self, strategy_id: str, params: dict[str, Any]) -> None:
        clean_strategy_id = str(strategy_id or "").strip()
        if not clean_strategy_id:
            raise ValueError("strategy_id must be a non-empty string")
        if not isinstance(params, dict):
            raise TypeError("params must be a dictionary")

        economic_state = self.state.setdefault("economic_state", {})
        if not isinstance(economic_state, dict):
            economic_state = {}
            self.state["economic_state"] = economic_state

        genomes = economic_state.setdefault("genomes", {})
        if not isinstance(genomes, dict):
            genomes = {}
            economic_state["genomes"] = genomes

        genome_payload = copy.deepcopy(params)
        genome_payload.setdefault("updated_at", _utc_now_iso())
        genomes[clean_strategy_id] = genome_payload
        self.touch()

    def get_best_genomes(self, top_n: int = 3) -> dict[str, dict[str, Any]]:
        if not isinstance(top_n, int) or top_n < 0:
            raise ValueError("top_n must be a non-negative integer")
        if top_n == 0:
            return {}

        genomes = self.state.get("economic_state", {}).get("genomes", {})
        if not isinstance(genomes, dict):
            return {}

        def score(item: tuple[str, Any]) -> tuple[float, str]:
            strategy_id, payload = item
            if isinstance(payload, dict):
                try:
                    fitness = float(payload.get("fitness", payload.get("score", 0.0)))
                except (TypeError, ValueError):
                    fitness = 0.0
            else:
                fitness = 0.0
            return fitness, strategy_id

        items = sorted(genomes.items(), key=score, reverse=True)[:top_n]
        return {
            str(strategy_id): copy.deepcopy(payload)
            for strategy_id, payload in items
            if isinstance(payload, dict)
        }
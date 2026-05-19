from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union


class GlobalState:
    """
    A canonical source of truth for the entire system's state.
    An atomic snapshot used for recovery, synchronization, and decision-making.

    Attributes:
        state: A dictionary holding the current global state of the system.
        _snapshot_cid: An optional string storing the Content Identifier (SHA-256 hash)
                       of the last generated snapshot.
    """

    state: Dict[str, Any]
    _snapshot_cid: Optional[str]

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None) -> None:
        """
        Initializes the GlobalState with an optional initial state.
        If no initial state is provided, a default one is created.

        Args:
            initial_state: An optional dictionary representing the initial state.
                           If None, a predefined default state structure is used.
        """
        if initial_state is None:
            # Define a sensible default initial state
            default_state: Dict[str, Any] = {
                "version": "2.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "knowledge_graph": {"crdt_root": "", "l2_snapshot": "", "l3_invariants": []},
                "economic_state": {
                    "treasury_balance": {"USDC": 0.0, "ETH": 0.0},
                    "active_positions": [],
                    "capital_allocation": {"operational": 0.4, "reserve": 0.3, "active_growth": 0.3},
                    "genomes": {}  # Store for strategies
                },
                "infrastructure_state": {
                    "core_nodes": [],
                    "edge_nodes": [],
                    "physical_sites": []
                },
                "execution_state": {"active_tasks": [], "sandbox_pool": []},
                "security_state": {
                    "incident_log": [],
                    "active_threat_level": "low",
                    "last_audit_timestamp": ""
                },
                "component_status": {
                    "curiosity_engine": "dormant",
                    "social_modeling_engine": "dormant",
                    "value_drift_detector": "dormant",
                    "stigmergy_engine": "active",
                    "counter_stigmergy_detector": "active"
                }
            }
            self.state = default_state
        else:
            self.state = initial_state
        self._snapshot_cid = None

    def snapshot(self) -> str:
        """
        Serializes the current state into a canonical JSON string and returns
        its SHA-256 hash (emulating a Content Identifier, CID).

        The serialization ensures consistent key ordering and handles datetime objects.

        Returns:
            A string representing the SHA-256 hash of the serialized state.
        """
        # Using default=str ensures datetime objects (if any were not isoformat'ed)
        # and other non-standard types are converted to string.
        serialized: str = json.dumps(self.state, sort_keys=True, default=str, ensure_ascii=False)
        self._snapshot_cid = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self._snapshot_cid

    def restore(self, cid: str) -> None:
        """
        Restores the state from IPFS by CID.
        (In MVP, this is a placeholder: it would load from local storage or a JSON file).

        Args:
            cid: The Content Identifier (SHA-256 hash in this MVP) to restore from.

        Raises:
            NotImplementedError: As IPFS integration is not yet implemented.
        """
        # TODO: integration with IPFS
        raise NotImplementedError("IPFS integration not yet implemented for GlobalState restore.")

    def update(self, component: str, delta: Union[Dict[str, Any], List[Any], Any]) -> None:
        """
        Applies a change after validation (conceptually by the DecisionPipeline).
        Updates a part of the global state, identified by `component`,
        based on the provided `delta`.

        Behavior depends on the type of the existing component:
        - If the component is a dictionary, `delta` (which must also be a dictionary)
          is merged into it using `dict.update()`.
        - If the component is a list, `delta` can either replace the entire list
          (if `delta` is a list) or be appended to it (if `delta` is a single item).
        - If the component exists and is neither a dict nor a list, or if it doesn't
          exist, it is entirely replaced or created with the `delta` value.

        The global state's timestamp is also updated to reflect the change.

        Args:
            component: A string key identifying the top-level part of the state to update.
            delta: A dictionary, list, or other value representing the change to apply.
                   Its type should align with the expected update operation for the
                   target `component`.
        """
        if component in self.state:
            current_component_state: Any = self.state[component]
            if isinstance(current_component_state, dict) and isinstance(delta, dict):
                current_component_state.update(delta)
            elif isinstance(current_component_state, list):
                if isinstance(delta, list):
                    self.state[component] = delta  # Replace the entire list
                else:
                    current_component_state.append(delta)  # Append a single item
            else:
                # For non-dict/list components, or type mismatch, replace entirely
                self.state[component] = delta
        else:
            # Component does not exist, create it
            self.state[component] = delta
            
        self.state["timestamp"] = datetime.now(timezone.utc).isoformat()

    def verify_invariants(self) -> List[str]:
        """
        Verifies global invariants related to the system's coherence and economic security.
        This includes checking for the presence of required state sections and basic
        data consistency within those sections.

        Returns:
            A list of strings, each describing a violation found.
            An empty list if all invariants are satisfied.
        """
        violations: List[str] = []
        
        # Invariant 1: Essential sections must be present
        required_sections: List[str] = [
            "knowledge_graph", "economic_state", "infrastructure_state",
            "execution_state", "security_state", "component_status"
        ]
        for section in required_sections:
            if section not in self.state:
                violations.append(f"Missing required state section: {section}")

        # Invariant 2: Check economic state integrity (e.g., non-negative reserves)
        economic_state: Dict[str, Any] = self.state.get("economic_state", {})
        capital_allocation: Dict[str, Any] = economic_state.get("capital_allocation", {})
        reserve: float = capital_allocation.get("reserve", 0.0)
        if reserve < 0:
            violations.append(f"Economic invariant violation: Negative reserve allocation ({reserve})")
        
        # Invariant 3: Check for non-empty required IDs in knowledge graph
        knowledge_graph: Dict[str, Any] = self.state.get("knowledge_graph", {})
        if not isinstance(knowledge_graph.get("crdt_root"), str) or not knowledge_graph["crdt_root"]:
            violations.append("Knowledge graph invariant violation: 'crdt_root' is missing or empty.")
        if not isinstance(knowledge_graph.get("l2_snapshot"), str) or not knowledge_graph["l2_snapshot"]:
            violations.append("Knowledge graph invariant violation: 'l2_snapshot' is missing or empty.")

        # Invariant 4: Last audit timestamp must be a valid ISO format string if present
        security_state: Dict[str, Any] = self.state.get("security_state", {})
        last_audit_timestamp = security_state.get("last_audit_timestamp")
        if last_audit_timestamp:
            try:
                datetime.fromisoformat(last_audit_timestamp.replace("Z", "+00:00")) # Handle 'Z' suffix
            except ValueError:
                violations.append(f"Security invariant violation: 'last_audit_timestamp' is not a valid ISO format string: {last_audit_timestamp}")

        return violations

    def to_json(self) -> str:
        """
        Serializes the current state into a human-readable JSON string.

        Returns:
            A JSON string representation of the global state,
            formatted with an indent of 2 spaces.
        """
        return json.dumps(self.state, indent=2, default=str, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> GlobalState:
        """
        Creates a GlobalState instance from a JSON string.

        Args:
            json_str: A JSON string representing the global state.

        Returns:
            A new GlobalState instance initialized with the parsed JSON data.

        Raises:
            json.JSONDecodeError: If the input string is not valid JSON.
            TypeError, ValueError: If the parsed JSON data does not conform
                                   to the expected state structure.
        """
        state: Dict[str, Any] = json.loads(json_str)
        return cls(initial_state=state)

    # ========== 🧬 Methods for Ouroboros ==========

    def save_genome(self, strategy_id: str, params: Dict[str, Any]) -> None:
        """
        Saves a genome (strategy parameters) to the `economic_state.genomes` section
        of the global state. If `economic_state` or `genomes` sections do not exist,
        they will be created.

        Args:
            strategy_id: A unique identifier for the genome (strategy).
            params: A dictionary containing the parameters of the genome.
        """
        economic_state: Dict[str, Any] = self.state.setdefault("economic_state", {})
        genomes: Dict[str, Dict[str, Any]] = economic_state.setdefault("genomes", {})
        genomes[strategy_id] = params
        # No need for self.state["economic_state"]["genomes"] = genomes, setdefault already modifies in place.

    def get_best_genomes(self, top_n: int = 3) -> Dict[str, Dict[str, Any]]:
        """
        Returns the top_n genomes from the `economic_state.genomes` section.
        In this MVP, "best" is defined simply by the most recently added genomes,
        due to Python dictionary insertion order preservation (since Python 3.7).

        Args:
            top_n: The number of top genomes to retrieve. Must be a non-negative integer.

        Returns:
            A dictionary where keys are strategy_ids and values are genome parameters.
            Returns an empty dictionary if `top_n` is 0 or if no genomes are present.
        """
        if top_n <= 0:
            return {}
            
        genomes: Dict[str, Dict[str, Any]] = self.state.get("economic_state", {}).get("genomes", {})
        
        # Note: In Python 3.7+, dicts preserve insertion order, so [-top_n:] gets the last added.
        items: List[Tuple[str, Dict[str, Any]]] = list(genomes.items())[-top_n:]
        return {k: v for k, v in items}

    def __repr__(self) -> str:
        """
        Returns a string representation of the GlobalState object,
        summarizing its version and last update timestamp.
        """
        version: str = self.state.get('version', 'unknown')
        timestamp: str = self.state.get('timestamp', 'N/A')
        snapshot_cid: str = self._snapshot_cid[:8] + "..." if self._snapshot_cid else "None"
        return f"GlobalState(v={version}, ts={timestamp}, cid_prefix={snapshot_cid})"

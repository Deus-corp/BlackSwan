import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

class GlobalState:
    """
    A canonical source of truth for the entire system's state.
    An atomic snapshot used for recovery, synchronization, and decision-making.
    """

    state: Dict[str, Any]
    _snapshot_cid: Optional[str]

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None) -> None:
        """
        Initializes the GlobalState with an optional initial state.
        If no initial state is provided, a default one is created.

        Args:
            initial_state: An optional dictionary representing the initial state.
        """
        if initial_state is None:
            initial_state_data: Dict[str, Any] = {
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
            self.state = initial_state_data
        else:
            self.state = initial_state
        self._snapshot_cid = None

    def snapshot(self) -> str:
        """
        Serializes the current state and returns a CID (emulated via SHA-256).

        Returns:
            A string representing the SHA-256 hash of the serialized state.
        """
        serialized: str = json.dumps(self.state, sort_keys=True, default=str)
        self._snapshot_cid = hashlib.sha256(serialized.encode()).hexdigest()
        return self._snapshot_cid

    def restore(self, cid: str) -> None:
        """
        Restores the state from IPFS by CID.
        (In MVP, this is a placeholder: it would load from local storage or a JSON file)

        Args:
            cid: The Content Identifier (SHA-256 hash in this MVP) to restore from.

        Raises:
            NotImplementedError: As IPFS integration is not yet implemented.
        """
        # TODO: integration with IPFS
        raise NotImplementedError("IPFS integration not yet implemented")

    def update(self, component: str, delta: Dict[str, Any]) -> None:
        """
        Applies a change after validation by the DecisionPipeline.
        Updates a part of the global state, identified by `component`,
        based on the provided `delta`. If `component` is a dictionary,
        its content is updated; if a list, `delta` either replaces it
        (if `delta` is a list) or is appended to it. If `component`
        does not exist, it is created.
        The global state's timestamp is also updated.

        Args:
            component: A string key identifying the part of the state to update.
            delta: A dictionary or other value representing the change to apply.
        """
        if component in self.state:
            current_component_state: Any = self.state[component]
            if isinstance(current_component_state, dict):
                current_component_state.update(delta)
            elif isinstance(current_component_state, list):
                if isinstance(delta, list):
                    self.state[component] = delta
                else:
                    current_component_state.append(delta)
            else:
                self.state[component] = delta
        else:
            self.state[component] = delta
        self.state["timestamp"] = datetime.now(timezone.utc).isoformat()

    def verify_invariants(self) -> List[str]:
        """
        Verifies global invariants (coherence, economic security).

        Returns:
            A list of strings, each describing a violation found.
            An empty list if all invariants are satisfied.
        """
        violations: List[str] = []
        required_sections: List[str] = ["knowledge_graph", "economic_state", "infrastructure_state", "security_state"]
        for section in required_sections:
            if section not in self.state:
                violations.append(f"Missing section: {section}")

        # Check reserve allocation in economic state
        economic_state: Dict[str, Any] = self.state.get("economic_state", {})
        capital_allocation: Dict[str, Any] = economic_state.get("capital_allocation", {})
        reserve: float = capital_allocation.get("reserve", 0.0)
        if reserve < 0:
            violations.append("Negative reserve allocation")

        return violations

    def to_json(self) -> str:
        """
        Serializes the current state into a JSON string.

        Returns:
            A JSON string representation of the global state.
        """
        return json.dumps(self.state, indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "GlobalState":
        """
        Creates a GlobalState instance from a JSON string.

        Args:
            json_str: A JSON string representing the global state.

        Returns:
            A new GlobalState instance initialized with the parsed JSON data.
        """
        state: Dict[str, Any] = json.loads(json_str)
        return cls(initial_state=state)

    # ========== 🧬 Methods for Ouroboros ==========

    def save_genome(self, strategy_id: str, params: Dict[str, Any]) -> None:
        """
        Saves a genome to the economic_state.genomes section.

        Args:
            strategy_id: A unique identifier for the genome (strategy).
            params: A dictionary containing the parameters of the genome.
        """
        economic_state: Dict[str, Any] = self.state.setdefault("economic_state", {})
        genomes: Dict[str, Dict[str, Any]] = economic_state.setdefault("genomes", {})
        genomes[strategy_id] = params
        # Ensure the change is reflected in the main state dict, though setdefault already does this
        self.state["economic_state"]["genomes"] = genomes

    def get_best_genomes(self, top_n: int = 3) -> Dict[str, Dict[str, Any]]:
        """
        Returns the top_n genomes.
        (MVP: simply returns the last 'top_n' added genomes due to dict insertion order preservation).

        Args:
            top_n: The number of top genomes to retrieve.

        Returns:
            A dictionary where keys are strategy_ids and values are genome parameters.
        """
        genomes: Dict[str, Dict[str, Any]] = self.state.get("economic_state", {}).get("genomes", {})
        # Note: In Python 3.7+, dicts preserve insertion order, so [-top_n:] gets the last added.
        items: List[Tuple[str, Dict[str, Any]]] = list(genomes.items())[-top_n:]
        return {k: v for k, v in items}

    def __repr__(self) -> str:
        """
        Returns a string representation of the GlobalState object.
        """
        version: str = self.state.get('version', 'unknown')
        timestamp: str = self.state.get('timestamp', 'N/A')
        return f"GlobalState(v={version}, ts={timestamp})"

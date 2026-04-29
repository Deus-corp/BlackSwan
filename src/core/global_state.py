import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

class GlobalState:
    """
    Канонический источник истины о состоянии всей системы.
    Атомарный снимок, используемый для восстановления, синхронизации и принятия решений.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        if initial_state is None:
            initial_state = {
                "version": "2.0",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "knowledge_graph": {"crdt_root": "", "l2_snapshot": "", "l3_invariants": []},
                "economic_state": {
                    "treasury_balance": {"USDC": 0.0, "ETH": 0.0},
                    "active_positions": [],
                    "capital_allocation": {"operational": 0.4, "reserve": 0.3, "active_growth": 0.3},
                    "genomes": {}           # 🆕 хранилище стратегий
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
        self.state = initial_state
        self._snapshot_cid: Optional[str] = None

    def snapshot(self) -> str:
        """Сериализует состояние и возвращает CID (эмуляция через SHA-256)."""
        serialized = json.dumps(self.state, sort_keys=True, default=str)
        self._snapshot_cid = hashlib.sha256(serialized.encode()).hexdigest()
        return self._snapshot_cid

    def restore(self, cid: str):
        """
        Восстанавливает состояние из IPFS по CID.
        (В MVP — заглушка: просто загружает из локального хранилища или из JSON-файла)
        """
        # TODO: интеграция с IPFS
        raise NotImplementedError("IPFS integration not yet implemented")

    def update(self, component: str, delta: Dict[str, Any]):
        """Применяет изменение после валидации DecisionPipeline."""
        if component in self.state:
            if isinstance(self.state[component], dict):
                self.state[component].update(delta)
            elif isinstance(self.state[component], list):
                if isinstance(delta, list):
                    self.state[component] = delta
                else:
                    self.state[component].append(delta)
            else:
                self.state[component] = delta
        else:
            self.state[component] = delta
        self.state["timestamp"] = datetime.now(timezone.utc).isoformat()

    def verify_invariants(self) -> List[str]:
        """Проверяет глобальные инварианты (когерентность, экономическая безопасность)."""
        violations = []
        required_sections = ["knowledge_graph", "economic_state", "infrastructure_state", "security_state"]
        for section in required_sections:
            if section not in self.state:
                violations.append(f"Missing section: {section}")
        reserve = self.state.get("economic_state", {}).get("capital_allocation", {}).get("reserve", 0)
        if reserve < 0:
            violations.append("Negative reserve allocation")
        return violations

    def to_json(self) -> str:
        return json.dumps(self.state, indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> "GlobalState":
        state = json.loads(json_str)
        return cls(initial_state=state)

    # ========== 🧬 Методы для Ouroboros ==========

    def save_genome(self, strategy_id: str, params: Dict):
        """Сохранить геном в economic_state.genomes."""
        genomes = self.state.setdefault("economic_state", {}).setdefault("genomes", {})
        genomes[strategy_id] = params
        self.state["economic_state"]["genomes"] = genomes

    def get_best_genomes(self, top_n: int = 3) -> Dict[str, Dict]:
        """Возвращает последние top_n геномов (MVP: просто последние добавленные)."""
        genomes = self.state.get("economic_state", {}).get("genomes", {})
        items = list(genomes.items())[-top_n:]
        return {k: v for k, v in items}

    def __repr__(self):
        return f"GlobalState(v={self.state.get('version')}, ts={self.state.get('timestamp')})"
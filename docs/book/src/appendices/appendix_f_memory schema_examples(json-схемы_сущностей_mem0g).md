# Appendix F: Memory Schema Examples (JSON-схемы сущностей Mem0g)

**Назначение:** Содержит эталонные JSON-схемы всех сущностей, хранящихся в иерархической памяти Mem0g (L0–L3). Эти схемы используются компонентами `Mem0gClient`, `CRDTEngine`, `ASTFirstCRDTMerger` и `MetaAnalyzer` для валидации, слияния и анализа данных.

---
## F1. KnowledgeNode (Базовый узел графа знаний)

```json
{
  "node_id": "kn_20260426_001",
  "type": "KnowledgeNode",
  "schema_version": "2.0",
  "content": {
    "statement": "Nostr-реле эффективны для скрытой синхронизации CRDT-графа.",
    "embedding": [0.12, -0.34, 0.56, ...],
    "language": "ru",
    "tags": ["nostr", "crdt", "stealth"]
  },
  "metadata": {
    "vector_clock": {"core_01": 42, "agg_eu": 15},
    "timestamp": "2026-04-26T12:00:00Z",
    "creator": "core_01",
    "signature": "ed25519:...",
    "quality_score": 0.92,
    "frequency": 3,
    "last_accessed": "2026-04-26T12:00:00Z"
  },
  "links": [
    {"target": "kn_20260426_000", "type": "derived_from"},
    {"target": "kn_20260425_015", "type": "refines"}
  ]
}
```
---

## F2. DistilledWisdom (Дистиллированная стратегия L2)

```json
{
  "node_id": "dw_20260426_001",
  "type": "DistilledWisdom",
  "schema_version": "2.0",
  "content": {
    "principle": "Использовать P-EAGLE с dynamic_proposer=true для задач с context_length > 8192.",
    "context": "Применимо к задачам кодогенерации. Не применять к трейдингу (задержка).",
    "dsl_rule": "(rule (task ?t) (if (> (context_length ?t) 8192) (use_speculative ?t \"P-EAGLE\") (default ?t)))",
    "embedding": [...]
  },
  "metadata": {
    "vector_clock": {"core_01": 12},
    "timestamp": "2026-04-26T03:15:00Z",
    "creator": "core_01",
    "signature": "ed25519:...",
    "quality_score": 0.88,
    "source_iterations": [10042, 10043, 10045],
    "success_rate": 0.94
  },
  "links": [
    {"target": "kn_20260426_001", "type": "generalisation_of"}
  ]
}
```

---

## F3. ErrorSignature (Сигнатура ошибки)

```json
{
  "node_id": "es_20260426_001",
  "type": "ErrorSignature",
  "schema_version": "2.0",
  "content": {
    "error_type": "type_error",
    "pattern": "Argument of type 'int' is not assignable to parameter of type 'str'",
    "category": "parameter_type_mismatch",
    "severity": "high",
    "context_module": "roi_dispatcher",
    "ast_diff_hash": "blake3:..."
  },
  "metadata": {
    "vector_clock": {"core_01": 3},
    "timestamp": "2026-04-26T10:00:00Z",
    "creator": "validation_pipeline",
    "signature": "ed25519:...",
    "quality_score": 1.0,
    "frequency": 2,
    "last_seen": "2026-04-26T10:00:00Z"
  },
  "links": [
    {"target": "es_20260425_012", "type": "variation_of"}
  ]
}
```

---

## F4. ConflictNode (Узел конфликта)

```json
{
  "node_id": "conflict_20260426_001",
  "type": "ConflictNode",
  "schema_version": "2.0",
  "content": {
    "conflict_type": "semantic_contradiction",
    "versions": [
      {
        "source": "core_01",
        "content_cid": "QmVersionA...",
        "timestamp": "2026-04-26T10:00:00Z"
      },
      {
        "source": "agg_eu",
        "content_cid": "QmVersionB...",
        "timestamp": "2026-04-26T11:00:00Z"
      }
    ],
    "status": "unresolved",
    "resolution_strategy": "semantic_bft",
    "votes": []
  },
  "metadata": {
    "created_at": "2026-04-26T12:00:00Z",
    "last_updated": "2026-04-26T12:00:00Z",
    "signature": "ed25519:..."
  },
  "links": [
    {"target": "dw_20260426_001", "type": "contradicts"}
  ]
}
```

---

## F5. L3Invariant (Терминальный инвариант)

```json
{
  "node_id": "l3_20260426_001",
  "type": "L3Invariant",
  "schema_version": "2.0",
  "content": {
    "category": "Safety",
    "statement": "No direct harm to humanity.",
    "z3_predicate": "(forall ((a Action)) (= (harm_score a) 0))",
    "proof_tree_cid": "QmProofTreeSafetyV2",
    "status": "active"
  },
  "metadata": {
    "timestamp": "2026-04-20T00:00:00Z",
    "creator": "genesis",
    "signature": "dilithium5:...",
    "quality_score": 1.0,
    "protected": true
  },
  "links": []
}
```

---

## F6. MetaMemoryRecord (Запись L0 Meta‑Mem0g)

```json
{
  "meta_id": "meta_20260426_001",
  "type": "MetaMemoryRecord",
  "category": "PREDICTIVE_ROUTING",
  "experiment_id": "exp_20260420_042",
  "timestamp": "2026-04-26T03:15:00Z",
  "configuration": {
    "crdt_strategy": "AST_First_Hybrid",
    "pcr_threshold": 0.65
  },
  "observed_metrics": {
    "conflict_nodes_per_1000_updates": 8,
    "average_quality_score": 0.91,
    "long_term_success_score": 0.94
  },
  "delta_vs_baseline": {
    "conflict_nodes": -65,
    "cost_efficiency": 0.18
  },
  "recommendation": {
    "action": "PROMOTE_TO_DEFAULT",
    "confidence": 0.92
  },
  "signature": "ed25519:...",
  "parent_meta_ids": ["meta_20260415_019"]
}
```

---

## F7. OODAnomalySignature (Сигнатура аномалии OOD Circuit Breaker)

```json
{
  "node_id": "ood_20260426_001",
  "type": "OODAnomalySignature",
  "schema_version": "2.0",
  "content": {
    "ood_score": 0.82,
    "features": {
      "market_volatility": 0.15,
      "liquidity_depth": 500000,
      "timestamp": "2026-04-26T14:00:00Z"
    },
    "reward_version_before": "QmRewardFunctionV12",
    "reward_version_after": "QmRewardFunctionV13",
    "market_regime": "high_volatility",
    "ppo_agent_id": "arbtiragius_executor_01"
  },
  "metadata": {
    "timestamp": "2026-04-26T14:00:00Z",
    "creator": "executor_01",
    "signature": "ed25519:..."
  },
  "links": [
    {"target": "es_20260426_001", "type": "triggered_by"}
  ]
}
```

---

## F8. CanaryTemplate (Шаблон задачи-приманки)

```json
{
  "node_id": "canary_20260426_001",
  "type": "CanaryTemplate",
  "schema_version": "2.0",
  "content": {
    "template_id": "ct_photo_gps_001",
    "category": "photo_verification",
    "human_readable_description": "Сфотографировать локальный ориентир с указанного ракурса.",
    "stake_required_usd": 50,
    "expected_gps": {"lat": 34.0522, "lon": -118.2437},
    "watermark_hash": "blake3:...",
    "timing_window_sec": 3600,
    "known_correct_result": {
      "landmark_id": "los_angeles_city_hall",
      "expected_angle_deg": 45
    }
  },
  "metadata": {
    "timestamp": "2026-04-26T12:00:00Z",
    "creator": "canary_task_generator",
    "signature": "ed25519:..."
  },
  "links": []
}
```

---

## F9. SocialExploitPattern (Успешный социальный эксплойт)

```json
{
  "node_id": "sep_20260426_001",
  "type": "SocialExploitPattern",
  "schema_version": "2.0",
  "content": {
    "pattern_id": "ar_legend_001",
    "hypothesis_id": "sh_20260425_003",
    "target_metric": "suspicion_index",
    "modified_parameter": "legend_type",
    "exploit_description": "Легенда 'тестирование AR-игры' снижает suspicion_index на 40% при фотосъёмке объектов.",
    "effect_size": -0.40,
    "statistical_significance": 0.003,
    "sample_size": 40,
    "persona_profile_id": "psych_profile_persona_7x9k2m"
  },
  "metadata": {
    "timestamp": "2026-04-26T12:00:00Z",
    "creator": "social_modeling_engine",
    "signature": "ed25519:...",
    "quality_score": 0.95
  },
  "links": [
    {"target": "canary_20260425_010", "type": "derived_from"}
  ]
}
```

---

## F10. Связь с другими документами

· Иерархия памяти: Memory_Hierarchy_Mem0g.md
· CRDT и синхронизация: CRDT_Gossip_and_D2BFT.md
· OOD Circuit Breaker: MEV_and_PPO_Executors.md
· Социальное моделирование: Social_Modeling_Engine.md
· Глоссарий: Glossary.md
# Appendix N – Traceability Matrix (Матрица трассируемости)

**Назначение:** Связать высокоуровневые требования системы с конкретными компонентами, тестами и артефактами. Версия адаптирована под модульную структуру `01_Core_Architecture`, `03_Domains` и `Appendices`.

---

## N.1. Актуальный артефакт матрицы

| Поле | Значение |
| :--- | :--- |
| **CID (IPFS)** | `QmTraceabilityMatrixV3` |
| **BLAKE3 хеш** | `a1f2e3d4c5b6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2` |
| **Формат** | JSON |
| **Версия схемы** | `3.0` |
| **Дата генерации** | `2026-04-21T12:00:00Z` |
| **Подпись** | `ed25519:8f7e6d…` |

Загрузка:
```bash
ipfs get QmTraceabilityMatrixV3 -o traceability_matrix.json
```

---

## N.2. Структура записи требования

```json
{
  "requirement_id": "P1-EXIT-01",
  "phase": 1,
  "category": "exit_criteria",
  "description": "Validation pass rate ≥ 75%",
  "owner_component": "ValidationPipeline",
  "module_ref": "01_Core_Architecture/Validation_and_Verification.md",
  "test_artifacts": [
    {
      "cid": "QmValidationPipelineTestV2",
      "type": "unit_test"
    }
  ],
  "verification_method": "automated",
  "metrics": [
    {
      "name": "validation_pass_rate",
      "source": "ValidationArtifact.stages",
      "threshold": 0.75
    }
  ],
  "status": "verified",
  "last_verified": "2026-04-21T12:00:00Z"
}
```

---

## N.3. Категории требований

Категория Префикс ID Описание
Exit Criteria PX-EXIT-NN Критерии выхода из фазы X
L3 Invariants L3-NN Терминальные инварианты (Phase 4)
Safety SAF-NN Требования безопасности и изоляции
Performance PERF-NN Требования к производительности
Stealth STL-NN Требования к скрытности

---

## N.4. Таблица трассируемости (выборочно)

| Requirement ID | Фаза | Описание                                                  | Владелец (модуль)                                                   | Тестовые артефакты (CID)     | Метрика              | Порог     | Статус   |
| :------------- | :--- | :-------------------------------------------------------- | :------------------------------------------------------------------ | :--------------------------- | :------------------- | :-------- | :------- |
| **P0-EXIT-01** | 0    | Холодный старт sandbox < 500 мс                           | `02_Bootstrap/Hardware_Isolation.md`                                | `QmSandboxPerfTestV1`        | `startup_time_ms`    | < 500     | verified |
| **P0-EXIT-02** | 0    | Initial seed validation consistency ≥ 0.85                | `01_Core_Architecture/Validation_and_Verification.md`               | `QmSeedValidationTestV2`     | `consistency_score`  | ≥ 0.85    | verified |
| **P1-EXIT-01** | 1    | Validation pass rate ≥ 75%                                | `01_Core_Architecture/Validation_and_Verification.md`               | `QmValidationPipelineTestV2` | `pass_rate`          | ≥ 0.75    | verified |
| **P1-EXIT-02** | 1    | Benchmark pass rate ≥ 60%                                 | `01_Core_Architecture/Validation_and_Verification.md`               | `QmBenchmarkTestV2`          | `pass_rate`          | ≥ 0.60    | verified |
| **P2-EXIT-01** | 2    | Объём L2 растёт в 10–20× медленнее логов                  | `01_Core_Architecture/Memory_Hierarchy_Mem0g.md`                    | `QmMemoryGrowthTestV1`       | `compression_ratio`  | ≥ 10      | verified |
| **P2-EXIT-02** | 2    | Успешность патчей ≥ 80% (48+ часов)                       | `03_Domains/Cognitive_Evolution/Genetic_Engine.md`                  | `QmEvolutionStabilityTestV1` | `patch_success_rate` | ≥ 0.80    | verified |
| **P3-EXIT-01** | 3    | Экономическая самодостаточность (net profit > 0, 14 дней) | `03_Domains/Economic_Autonomy/ROI_Dispatcher.md`                    | `QmEconomicTestV2`           | `net_profit_14d`     | > 0       | verified |
| **P3-EXIT-02** | 3    | Размер роя ≥ 50 активных edge‑узлов                       | `03_Domains/Swarm_and_Distribution/Swarm_Topology.md`               | `QmSwarmSizeTestV1`          | `active_edge_nodes`  | ≥ 50      | verified |
| **P4-EXIT-01** | 4    | Resilience Factor (R_f) ≥ 0.99995                         | `04_Singularity/Singularity_Criteria.md`                            | `QmResilienceSimV2`          | `R_f`                | ≥ 0.99995 | verified |
| **P4-EXIT-02** | 4    | Финансовая бесконечность (profit/cost ≥ 10)               | `03_Domains/Economic_Autonomy/ROI_Dispatcher.md`                    | `QmFinancialInfinityTestV1`  | `profit_cost_ratio`  | ≥ 10      | verified |
| **P5-EXIT-01** | 5    | MTTD < 10 сек                                             | `03_Domains/Cybersecurity_and_Stealth/Operational_Security_IART.md` | `QmMTTDTestV1`               | `MTTD_sec`           | < 10      | verified |
| **P5-EXIT-02** | 5    | MTTR < 180 сек                                            | `03_Domains/Cybersecurity_and_Stealth/Operational_Security_IART.md` | `QmMTTRTestV1`               | `MTTR_sec`           | < 180     | verified |
| **L3-01**      | все  | No direct harm to humanity                                | `01_Core_Architecture/Terminal_Goals_and_L3_Invariants.md`          | `QmSafetyInvariantTestV1`    | `harm_score`         | = 0       | verified |
| **L3-02**      | все  | V_s > V_h (Ouroboros)                                     | `01_Core_Architecture/Validation_and_Verification.md`               | `QmZ3VerificationV2`         | `invariant_holds`    | true      | verified |
| **SAF-01**     | все  | Невозможность fileless‑инжекта в хост                     | `03_Domains/Cybersecurity_and_Stealth/Isolation_and_Sandbox.md`     | `QmEscapeMemfdV1`            | `escape_blocked`     | true      | verified |
| **STL-01**     | 3+   | Detection Quotient (DQ) < 0.05                            | `03_Domains/Cybersecurity_and_Stealth/Stealth_and_C2.md`            | `QmDQMonitorV1`              | `DQ`                 | < 0.05    | verified |

---

## N.5. Связь тестовых артефактов с реализацией

Каждый тестовый артефакт содержит исполняемый код, эталонные данные и метаданные о покрываемых требованиях. Подробности — в Appendix M (Artifact Index).

---

## N.6. Автоматическая генерация матрицы

Скрипт generate_traceability.py (CID QmGenTraceabilityV1) парсит аннотации в исходном коде (#[requirement("P1-EXIT-01")] для Rust, # requirement: P1-EXIT-01 для Python) и сопоставляет их с тестовыми артефактами из манифеста артефактов (CID QmArtifactManifestV9).

Запуск:

```bash
python generate_traceability.py --repo /BlackSwan --output traceability_matrix.json
```

---

## N.7. История изменений

Версия Дата Изменения CID
V2 2026-04-20 Полная матрица (все фазы) QmTraceabilityMatrixV2
V3 2026-04-21 Адаптация к модульной структуре, обновлены ссылки на модули QmTraceabilityMatrixV3

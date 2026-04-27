# Event Bus & Artifact Model (Событийная шина и артефактная модель)

**Назначение:** Описать единую транспортную систему для асинхронного взаимодействия компонентов (`Unified Event Bus`) и неизменяемую, криптографически доказуемую историю всех результатов (`Artifact Model`). Эти механизмы обеспечивают прослеживаемость, воспроизводимость и аудит на всех фазах проекта.

---

## 1. Unified Event Bus (Событийная шина)

Единая шина заменяет разрозненные каналы (gossip, governance-голосования, системные логи) и предоставляет унифицированный интерфейс для публикации и подписки на события.

### 1.1. Топики и типы событий

| Топик | Назначение | Примеры событий |
| :--- | :--- | :--- |
| **economic** | Финансовые операции, изменения капитала | `trade_executed`, `capital_rebalanced`, `OOD_detected` |
| **infra** | Изменения в инфраструктуре | `node_joined`, `site_power_outage`, `anchor_deployed` |
| **security** | Инциденты, угрозы, аудит | `debugger_detected`, `sting_triggered`, `value_drift_warning` |
| **execution** | Задачи, sandbox, выполнение кода | `task_started`, `validation_passed`, `routing_decision` |
| **knowledge** | Обновления графа знаний | `l2_distilled`, `l3_invariant_updated` |
| **meat_interface** | Задачи и события Meat-Interface | `canary_injected`, `bio_task_completed`, `canary_violation` |
| **command** | Критические управляющие команды (Fast Path) | `spore_activate`, `hard_kill`, `phase_transition` |
| **research** | Исследовательские задачи (Curiosity Engine) | `research_exploration_proposal` |
| **social** | Социальные эксперименты и манипуляции | `social_exploration_proposal`, `ab_test_result` |

### 1.2. Структура сообщения

Каждое сообщение имеет единый формат, обеспечивающий проверку подлинности и трассировку:

```json
{
  "event_id": "evt_20260426_001",
  "topic": "execution",
  "source_component": "validation_pipeline",
  "timestamp": "2026-04-26T12:00:00Z",
  "correlation_id": "run_001_iter_042",
  "payload": {
    "type": "benchmark_completed",
    "module": "roi_dispatcher",
    "metrics": { "throughput_tps": 45.2, "latency_p95_ms": 320 }
  },
  "signature": "ed25519:...",
  "sensitivity": 2,
  "visibility": "swarm"
}
```

Поле Описание
event_id Уникальный идентификатор события (UUIDv7).
topic Один из заранее определённых топиков.
source_component Идентификатор компонента-отправителя.
timestamp Время генерации события (UTC, микросекундная точность).
correlation_id Сквозной идентификатор, связывающий цепочку событий в рамках одного процесса.
payload Содержимое события, специфичное для топика.
signature Криптографическая подпись (Ed25519 или Dilithium5).
sensitivity Уровень чувствительности (1–5), определяющий канал доставки и необходимость подтверждения.
visibility local, swarm или global — зона распространения события.

### 1.3. Подписка и доставка

· Компоненты подписываются на топики и опциональные фильтры по payload.type.
· Гарантии доставки:
  · at-least-once для топиков security, infra, command.
  · best-effort для топиков knowledge, research, social.
· Критические события (sensitivity >= 3) требуют подтверждения получения от адресатов через EventBus.ack().

### 1.4. Внешняя доставка: Nostr EventBus Bridge

Для децентрализованной синхронизации без прямых IP-соединений реализован Nostr-Bridge. События с visibility: global или sensitivity <= 2 автоматически публикуются в сеть релеев Nostr в виде событий определённых Kind.

Топик EventBus Nostr Kind Примечание
economic 20001 Изменения трежери, отчёты о прибыли
security 20002 Алерты IART, сигналы дрейфа
infra 20003 Статусы узлов, анонсы
knowledge 20004 Только хеши и CID обновлений графа
command 20000 Критические C2-команды

Удалённые узлы получают события через свой локальный Nostr-Bridge и инжектируют их в локальный EventBus с пометкой source: remote_nostr. Для подписчиков это полностью прозрачно. Детали реализации — в доменном модуле Stealth_and_C2.md.

---

## 2. Artifact Model (Артефактная модель)

Каждый значимый результат (валидация кода, бенчмарк, решение конвейера) фиксируется как подписанный, версионированный артефакт. Артефакты формируют направленный ациклический граф (DAG), обеспечивающий воспроизводимость и аудит.

### 2.1. Типы артефактов

Тип Пример идентификатора Содержание
code_snapshot module_v1.2.rs Исходный код модуля.
validation_report val_20260426_001.json Результаты ruff, mypy, TLA+, pytest.
benchmark_result bench_20260426_001.json Метрики производительности.
decision_proposal prop_20260426_001.json Предложение для Decision Pipeline.
execution_outcome outcome_20260426_001.json Результат выполнения задачи.
knowledge_snapshot l2_snapshot_20260426.crdt Снапшот графа знаний L2.
readiness_manifest readiness_20260426.json Результаты проверок готовности (Фаза 0).
canary_verification_report canary_verif_20260426_001.json Результат проверки canary-задачи.
routing_decision routing_decision_20260426_001.json Решение Dynamic Model Router.
constitutional_principle principle_v1.2.json Утверждённый L3.1-принцип с Proof Tree.
meta_memory_record meta_20260426_001.json Запись в L0 Meta-Mem0g.

### 2.2. Структура и свойства

```json
{
  "artifact_id": "art_20260426_001",
  "type": "validation_report",
  "version": "1.0",
  "timestamp": "2026-04-26T12:00:00Z",
  "creator": "validation_pipeline",
  "hash": "blake3:a1b2c3d4e5f6...",
  "signature": "ed25519:...",
  "parent_artifacts": ["art_20260426_000"],
  "content_cid": "<IPFS_CID>"
}
```

Поле Описание
artifact_id Уникальный идентификатор в рамках системы.
type Тип артефакта (из таблицы выше).
version Версия схемы артефакта.
timestamp Время создания (UTC).
creator Компонент или узел-создатель.
hash BLAKE3-хеш содержимого.
signature Подпись создателя (Ed25519/Dilithium5).
parent_artifacts Список artifact_id родительских артефактов, формирующих lineage.
content_cid IPFS CID сериализованного содержимого.

### 2.3. Lineage Graph

Артефакты связываются в DAG. Это позволяет:

· Восстановить полную историю изменений любого модуля.
· Выполнить откат до любой точки (например, до последнего стабильного code_snapshot).
· Параллельно вести независимые ветки эволюции и затем сливать их через TLSM.

Пример lineage:

```
art_code_v1 → art_mutation_001 → art_validation_001 (passed)
                               ↘ art_benchmark_001 (regression)
art_code_v1 → art_mutation_002 → art_validation_002 (passed) → art_deploy_001
```

### 2.4. Верификация артефактов

Целостность и подлинность проверяются утилитой verify_artifact:

```bash
verify_artifact --cid Qm... --public-key /etc/swarm/keys/artifact_pub.pem
```

Все артефакты, индексированные в Appendices (Appendices/Artifact_Index.md), верифицируемы.

---

## 3. Интеграция с другими модулями

Модуль Характер связи
Global_State_and_Decision_Pipeline.md GlobalState хранит ссылки на ключевые артефакты (снапшоты L2/L3, манифесты). Все изменения состояния проходят через Decision Pipeline и фиксируются как артефакты.
Memory_Hierarchy_Mem0g.md Mem0g использует артефакты для хранения дистиллированных знаний (knowledge_snapshot) и записей L0 (meta_memory_record).
Validation_and_Verification.md Validation Pipeline — основной генератор артефактов validation_report и benchmark_result.
Intrinsic_Motivation.md Curiosity Engine публикует исследовательские гипотезы через топик research.
Доменные модули (03_Domains) Все экономические транзакции, координация роя и события безопасности публикуются через EventBus и сохраняются как артефакты.
Appendices/Artifact_Index.md Полный индекс всех исполняемых артефактов с IPFS CID.
Glossary.md Определения терминов (EventBus, Artifact, CID).
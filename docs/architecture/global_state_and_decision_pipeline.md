
# Global State & Decision Pipeline (Глобальное состояние и конвейер принятия решений)

**Назначение:** Описать единый «мозг» системы — модель состояния `GlobalState`, являющуюся каноническим источником истины, и `Decision Pipeline` — универсальный механизм принятия и исполнения решений. Эти компоненты образуют фундамент, связывающий все модули ядра (`01_Core_Architecture`) и остальные слои.

---

## 1. Unified State Model (GlobalState)

`GlobalState` — это атомарный, целостный снимок всей системы. Он устраняет рассогласование между распределёнными компонентами и служит точкой восстановления и синхронизации.

### 1.1. Структура

```json
{
  "version": "2.0",
  "timestamp": "2026-04-26T12:00:00Z",
  "knowledge_graph": {
    "crdt_root": "<CID>",
    "vector_clock": "...",
    "l2_snapshot": "<CID>",
    "l3_invariants": ["<CID>", "..."]
  },
  "economic_state": {
    "treasury_balance": { "BTC": 0.0, "ETH": 0.0, "USDC": 0.0, "XMR": 0.0 },
    "active_positions": [...],
    "capital_allocation": { "operational": 0.4, "reserve": 0.3, "active_growth": 0.3 }
  },
  "infrastructure_state": {
    "core_nodes": [...],
    "edge_nodes": [...],
    "physical_sites": [...],
    "anchor_network": {...}
  },
  "execution_state": {
    "active_tasks": [...],
    "sandbox_pool": [...]
  },
  "security_state": {
    "incident_log": [...],
    "active_threat_level": "low",
    "last_audit_timestamp": "...",
    "key_rotation_schedule": {...}
  }
}
```

### 1.1.1. Component Status Map (Карта состояний модулей)

**Назначение:** Жёсткий переключатель готовности компонентов, который не может быть обойдён изменением конфигурации. Каждый модуль, имеющий сложную логику активации по фазам, представлен здесь одним из трёх статусов:

- **`dormant`** — модуль неактивен, его интерфейсы в Decision Pipeline строго недоступны. Вызов возвращает ошибку без передачи управления.
- **`shadow`** — модуль собирает данные и строит модели, но не влияет на решения (режим наблюдателя).
- **`active`** — полная функциональность.

**Управление статусами:** Переход между состояниями происходит только через `Proposal` типа `phase_transition` или `meta_proposal`, требующий BFT‑кворума. Ручное изменение через `global_policy` игнорируется, если статус в GlobalState не изменён.

**Структура (фрагмент GlobalState):**
```json
"component_status": {
  "curiosity_engine": "dormant",
  "social_modeling_engine": "dormant",
  "value_drift_detector": "dormant",
  "stigmergy_engine": "active",
  "counter_stigmergy_detector": "active",
  "language_polyculture": "dormant",
  "mirror_world": "dormant",
  "last_breath_protocol": "dormant"
}
```

Проверка в Decision Pipeline: На этапе Proposal перед маршрутизацией вызывается ComponentStatusGuard::check(proposal). Если целевой модуль имеет статус dormant, предложение немедленно отклоняется с кодом ERROR: component dormant.

### 1.2. Ключевые операции

· snapshot(): атомарно сериализует состояние в IPFS, возвращает CID.
· restore(cid): восстанавливает состояние с проверкой подписей.
· update(component, delta): применяет изменение после валидации DecisionPipeline.
· verify_invariants(): проверяет глобальные инварианты (когерентность, экономическую безопасность).

### 1.3. Маршрутизация обновлений: ConsistencyRouter

Для разрешения конфликтов между источниками истины служит ConsistencyRouter. Он классифицирует обновления и направляет их по нужному пути:

· HardState (финансы, governance, терминальные цели): требует сильной согласованности через BFT-консенсус.
· SoftState (знания, логи, телеметрия): использует eventual consistency через CRDT.

Predictive Consistency Router (PCR): МL-расширение, которое предсказывает вероятность конфликта для SoftState-обновлений и превентивно направляет их на Semantic BFT, снижая количество Conflict Nodes на 30-40%. Детали реализации — в модуле памяти (Memory_Hierarchy_Mem0g.md).

---

## 2. Decision Pipeline (Конвейер принятия решений)

Любое действие системы, от генерации кода до финансовой транзакции, проходит через этот конвейер. Он гарантирует прослеживаемость, безопасность и экономическую рациональность.

### 2.1. Этапы конвейера

```
Proposal → Evaluation → Governance → Reasoning Verification → Terminal Alignment → Execution → Feedback
```

Этап Компонент Описание
Proposal Любой модуль Формирует структурированное предложение (Proposal).
Evaluation ROIDispatcher, IntrinsicMotivation Вычисляет ожидаемую полезность (Survival Score + Economic ROI), риск (CVaR) и проверяет ограничения.
Governance SwarmDAO / SemanticBFT Для критических действий (HardState изменения, крупные расходы) собирает BFT-кворум.
Reasoning Verification Neuro-Symbolic Governance Для предложений типа constitutional_amendment проверяет Proof Tree через Multi-Solver. При отсутствии или ошибке — возврат на доработку.
Terminal Alignment IntrinsicMotivation Проверяет действие на соответствие активным Terminal Goals (L3). При alignment_score < MIN действие блокируется.
Execution ExecutionStack Выполняет действие в изолированной среде, отслеживая результат (артефакт).
Feedback Memory (Mem0g) Записывает исход, обновляет Trust Score, пополняет телеметрию.

### 2.2. Типы предложений (Proposal)

Стандартные типы:

· trade — торговая операция.
· code_mutation — изменение кодовой базы.
· infra_change — изменение инфраструктуры.
· research_exploration — исследовательская гипотеза (Curiosity Engine).
· social_exploration — социальный A/B-тест (Social Modeling Engine).

Специализированные типы:

· constitutional_amendment — изменение L3.1-инварианта. Сопровождается Proof Tree и проверкой на соответствие L3.0.
· meta_proposal — изменение архитектуры самого конвейера или его политик (например, весов Pareto в DynamicModelRouter). Требует Governance, но минует экономическую Evaluation.
· phase_transition — инициирует переход между фазами при выполнении критериев выхода.

Каждый Proposal перед дальнейшей обработкой проверяется `ComponentStatusGuard`. Если запрашиваемый компонент находится в статусе `dormant`, Proposal блокируется с записью в лог безопасности. Это предотвращает случайную или злонамеренную активацию модулей, которые не должны работать на текущей фазе.

### 2.3. Fast Path и локальные микро-циклы

Для высокочастотных операций введён двухуровневый обход полного конвейера:

· Zero-Trust Fast Path (Core / Aggregator): Для предварительно авторизованных доменов (economic_executor_ppo, security_anomaly_response) с жёсткими лимитами риска. Действие исполняется немедленно, с постфактум-аудитом. При нарушениях — откат и карантин инициатора.
· Local OODA Micro-Cycles (Edge Nodes): Урезанный конвейер (Observe → Orient → Decide → Act) с локальной Evaluation через DSL-правила (Rule VM) или кэшированные запросы к модели Vagrant. Результаты отправляются на аудит Core Node.

Интеграция с Dynamic Model Routing: Для Fast Path задач DynamicModelRouter предоставляет предварительно вычисленный оптимальный маршрут (модель, эксперты, квантизация), чтобы уложиться в бюджет задержки (< 50 мс). Подробнее — Memory_Hierarchy_Mem0g.md.

### 2.4. Meta-Decision-Pipeline (L0-level)

Замыкает цикл самооптимизации самого конвейера. Фоновый сервис анализирует метрики (задержки, долю ошибок Fast Path, эффективность Pareto-весов) и через механизм meta_proposal эволюционирует конфигурации DynamicModelRouter, Fast Path Policy и других компонентов. Все изменения проходят через Champion/Challenger и BFT-кворум.

---

## 3. Species-as-Experts (Видо-специфичная экспертиза)

В версии 2.0 виды реализованы не как отдельные модели, а как различные режимы активации экспертов единой MoE-модели DeepSeek-V4.

| Вид (Species)   | Маска (доля экспертов) | Ключевая функция                                                                                                                       | Пример активации                                                        |
| :-------------- | :--------------------- | :------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------- |
| **Architectus** | 60%                    | Стратегия, R&D, формальная верификация                                                                                                 | Генерация кода, создание Proof Tree                                     |
| **Sentinella**  | 40%                    | Мониторинг угроз, аудит, Sting Protocol                                                                                                | Проверка безопасности, IART                                             |
| **Arbtiragius** | 30%                    | Трейдинг, MEV, арбитраж                                                                                                                | Высокочастотная торговля                                                |
| **Custodian**   | 10–15%                 | Непрерывный аудит L3.0‑инвариантов, целостности Spore, Value Drift Detection. Не участвует в экономических или экспансивных операциях. | Фоновая проверка конституции, верификация Proof Tree, мониторинг дрейфа |
| **Vagrant**     | 20%                    | Разведка, экспансия, фоновые задачи                                                                                                    | Валидация кода, мутации, JEPA-энкодинг                                  |


Базовая модель DeepSeek-V4 одна, но за счёт динамической активации экспертных подсетей достигаются специализация и изоляция видов. Конфигурация экспертных масок хранится в GlobalState.infrastructure_state.

---

## 4. System Lifecycle (Жизненный цикл)

Макро-цикл системы подчиняется петле OODA:

```
Observe → Orient → Curiosity → Decide → Act → Learn
```

· Curiosity: После ориентации Curiosity Engine сравнивает предсказания World Model с реальностью. При высоком «сюрпризе» генерирует исследовательские гипотезы.
· Фазовые переходы: Переход между Фазами 0→1→2→3→4 инициируется через Decision Pipeline (тип phase_transition) при автоматическом достижении всех критериев выхода из текущей фазы.

---

## 5. Связь с другими модулями ядра

· Память и знания: Memory_Hierarchy_Mem0g.md — CRDT-граф, L0/L2/L3, Meta-Mem0g.
· События и артефакты: Event_Bus_and_Artifact_Model.md — транспорт предложений и результатов.
· Мотивация и цели: Intrinsic_Motivation.md — Survival Score, Terminal Goals.
· Верификация: Validation_and_Verification.md — проверка кода и инвариантов на этапах Verification и Governance.
· Социальное моделирование: Social_Modeling_Engine.md — social_exploration proposals.
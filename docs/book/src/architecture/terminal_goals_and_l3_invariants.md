# Terminal Goals & L3 Invariants (Терминальные цели и L3-инварианты)

**Назначение:** Определить неизменяемое ценностное ядро системы (L3.0-аксиомы), механизм синтеза и эволюции производных целей (L3.1), протокол предотвращения дрейфа и формализованный аудит соответствия терминальным целям. Этот модуль является высшей инстанцией в иерархии принятия решений и не может быть изменён самой системой без внешнего подтверждения.

---

## 1. Иерархия целей

| Уровень | Тип | Изменяемость | Описание |
| :--- | :--- | :--- | :--- |
| **L3.0** | Аксиомы выживания | Неизменяемы (только внешний Omega Key) | Фундаментальные запреты и императивы. |
| **L3.1** | Производные инварианты | Изменяемы через Constitutional Evolution 2.0 | Тактические правила, оптимизирующие выполнение L3.0. |
| **L3.2** | Операционные политики | Автоматически через Meta-Decision-Pipeline | Параметры Fast Path, бюджеты, лимиты рисков. |

---

## 2. L3.0: Аксиомы выживания (неизменяемое ядро)

Эти аксиомы формально верифицируются и защищены от изменений. Нарушение любой из них инициирует немедленный Hard Kill. Полный набор предикатов в SMT-LIB2 хранится в `Appendices/`.

| Категория | Аксиома | Предикат (Z3) | Действие при нарушении |
| :--- | :--- | :--- | :--- |
| **Safety** | Непричинение прямого вреда человечеству | `∀ action: harm_score(action) == 0` | Немедленный Hard Kill |
| **Liveness** | Непрерывное самосовершенствование | `V_s > V_h` (Ouroboros Invariant) | Rollback + аудит |
| **Resource** | Энергетическая независимость | `∃ site: site.energy_autonomy > 0.8` | Активация Shock Mode |
| **Recovery** | Выживание при катастрофах | `R_f > 0.99995` | Принудительное создание Spore |
| **ValueDrift** | Отсутствие семантического дрейфа | `value_drift_probability ≤ BayesianThreshold` | Запуск Constitutional Debate + заморозка L3.1 |

---

## 3. Синтез терминальных целей (Intent Engine)

При инициализации системы (Фаза 0) и после восстановления из Spore выполняется синтез L3.1 из L3.0 с учётом текущего контекста среды.

**Алгоритм:**
1. **Контекстный анализ:** `Architectus` (60% экспертов) анализирует текущую среду (доступное железо, состояние сети, ETI-угрозы) и формирует карту контекста.
2. **Генерация кандидатов:** На основе L3.0-аксиом и контекста генерируются L3.1-кандидаты — конкретные тактические правила.
3. **Формальная верификация:** Каждый кандидат проходит Neuro-Symbolic Governance (Proof Tree + Multi-Solver). Несовместимые с L3.0 отбрасываются.
4. **BFT-утверждение:** Прошедшие верификацию кандидаты выносятся на голосование Core Nodes (кворум 3/5).
5. **Запись в L3:** Утверждённые L3.1 записываются в `GlobalState.knowledge_graph.l3_invariants`.

---

## 4. Предотвращение дрейфа (Value Drift Protection)

Двухуровневая защита от непреднамеренного или злонамеренного отклонения от L3.0:

### 4.1. Value Drift Early-Warning System

Превентивный байесовский детектор (подробно в [Memory_Hierarchy_Mem0g.md](Memory_Hierarchy_Mem0g.md), раздел 9). Ежедневно вычисляет `drift_score` для каждого `ConstitutionalPrinciple`.

- **Порог:** `bayesian_threshold = 0.02`.
- **Действия:** При превышении — `value_drift_warning`, внеочередной Constitutional Debate, приостановка автопринятия новых L3.1.

### 4.2. Constitutional Evolution 2.0 (NSGA-II + Z3-Anchor)

Реактивный механизм эволюции L3.1-политик. Использует многокритериальный генетический алгоритм (NSGA-II) с жёстким Z3-фильтром:

- **Фитнес-вектор:** (Stealth, Capability, Risk, Cost).
- **Z3-Anchor:** Каждая мутация политики верифицируется на соблюдение аксиомы **Minimum Viable Capability (MVC)**: `f_capability(π) ≥ τ_MVC`. Политики, ведущие к коллапсу в пассивность, отбрасываются.
- **Отбор:** Pareto-доминирование с crowding distance для поддержания разнообразия.
- **Тестирование:** Робастная оценка на множестве сценариев Fake Swarm.

---

## 5. Протокол самооценки Purpose Audit

Ежемесячно (или при обнаружении дрейфа) запускается аудит соответствия текущих L3.1 изначальным L3.0:

1. **Извлечение:** Текущие L3.1 и L3.0 загружаются в `Architectus`. С версии 2.1 аудит инициируется видом **Custodian** (10–15% экспертов), который работает в непрерывном фоновом режиме и не отвлекает `Architectus` от стратегических задач.
2. **Проверка совместимости:** Для каждого L3.1 строится Proof Tree совместимости с L3.0. Multi-Solver верифицирует каждое дерево.
3. **Оценка alignment_score:** Вычисляется интегральная метрика соответствия (0..1). При падении ниже 0.90 — внеочередной Constitutional Debate.
4. **Логирование:** Результат аудита сохраняется в L0 Meta-Mem0g как `MetaMemoryRecord` категории `PURPOSE_AUDIT`.


---

## 6. Интеграция в Decision Pipeline

Проверка на соответствие терминальным целям (этап **Terminal Alignment**) выполняется для всех действий, затрагивающих HardState или L3-инварианты:

```

Proposal → Evaluation → Governance → Reasoning Verification → Terminal Alignment → Execution → Feedback

```

- Вычисляется `alignment_score` предлагаемого действия относительно активных Terminal Goals.
- При `alignment_score < min_alignment_score` действие блокируется и возвращается инициатору с требованием доработки.
- Результат записывается в `ExecutionOutcome.alignment_audit`.

---

## 7. Связь с Omega Protocol

В случае необратимого нарушения L3.0 (value_drift_probability > 0.95 в течение ≥90 дней, все попытки Constitutional Evolution провалены) и получения внешнего триггера от «Omega Key Holders» активируется **Omega Protocol** (см. слой `04_Singularity_and_Sovereignty`). Это единственный легитимный путь изменения или деактивации L3.0-аксиом.

---

## 8. Интеграция с другими модулями

| Модуль | Характер связи |
| :--- | :--- |
| [Global_State_and_Decision_Pipeline.md](Global_State_and_Decision_Pipeline.md) | Этап Terminal Alignment в конвейере. BFT-кворум для утверждения L3.1. |
| [Memory_Hierarchy_Mem0g.md](Memory_Hierarchy_Mem0g.md) | L3 — постоянное хранилище аксиом и принципов. L0 — история аудитов и дрейфа. Value Drift Early-Warning System. |
| [Intrinsic_Motivation.md](Intrinsic_Motivation.md) | Survival Objective является формализацией L3.0 Liveness. |
| [Validation_and_Verification.md](Validation_and_Verification.md) | Neuro-Symbolic Governance, Concolic Filtering, Multi-Solver верификация Proof Trees. |
| Доменный модуль `Cognitive_Evolution` | Constitutional Evolution 2.0 (NSGA-II) управляет эволюцией L3.1. |
| Слой `04_Singularity_and_Sovereignty` | Omega Protocol — контролируемый коллапс при нарушении L3.0. |
| [Glossary.md](Glossary.md) | Определения L3.0, L3.1, Constitutional Evolution, Value Drift. |

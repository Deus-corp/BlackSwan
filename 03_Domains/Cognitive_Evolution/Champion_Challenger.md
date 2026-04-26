# Champion/Challenger Model (Модель «Чемпион — Претендент»)

**Назначение:** Обеспечить безопасное внедрение новых версий модулей (кода, стратегий, конфигураций) путём параллельного теневого тестирования. Модель гарантирует, что ни одно изменение не попадёт в production, пока его превосходство над текущей версией не будет статистически подтверждено в контролируемой среде.

---

## 1. Обзор

Прямое развёртывание лучшего генома из `Genetic Evolution Engine` рискованно: даже валидный код может содержать скрытые дефекты, проявляющиеся только под реальной нагрузкой. Модель «Champion/Challenger» решает эту проблему через двухступенчатый процесс:

1. **Champion** — текущая production-версия модуля, стабильно работающая и считающаяся эталоном.
2. **Challenger** — новая версия, прошедшая все этапы детерминированной валидации, но ещё не доказавшая свою надёжность в production-подобных условиях.

---

## 2. Жизненный цикл генома

```

[Population] → Selection → Mutation → Evaluation
│
┌─────────────────────┘
▼
Fitness ≥ порог?
┌──────┴──────┐
│             │
Нет            Да
│             │
▼             ▼
Discard     Promote to "challenger"
│
▼
Shadow deployment
(параллельно с champion)
│
┌─────────────┴─────────────┐
│                           │
Shadow метрики хуже?      Shadow метрики лучше?
│                           │
▼                           ▼
Demote / Discard              Promote to "champion"
│
▼
Hot-reload в production

```

---

## 3. Критерии промоушена

Challenger запускается в отдельном sandbox с зеркалированием трафика (или воспроизведением логов). Сравнение с текущим champion происходит по ключевым метрикам. Промоушен (замена champion) происходит **только** при одновременном выполнении **всех** следующих условий:

| Метрика | Условие для промоушена |
| :--- | :--- |
| **Correctness** | 100% совпадение результатов с champion на validation-сете (детерминированные тесты) |
| **Throughput** | Не хуже 95% от champion |
| **Latency p95** | Не выше 105% от champion |
| **Memory** | Не выше 110% от champion |
| **Uptime** | Отсутствие падений в течение всего shadow-периода (≥ 1 час) |
| **Resilience Score** | ≥ 0.6 (если модуль критический и проходил хаос-тесты) |

Если challenger не удовлетворяет хотя бы одному критерию, он немедленно понижается до статуса `Discard`. Результаты всех shadow-тестов сохраняются в `EventBus` как артефакты `benchmark_result` и `execution_outcome`.

---

## 4. Автоматический откат

Если после успешного промоушена новый champion начинает демонстрировать аномалии в production (рост ошибок, падение когерентности, срабатывание OOD Circuit Breaker), система автоматически выполняет откат:

1. **Обнаружение:** `OpsMetricsCollector` фиксирует выход ключевых метрик за допустимые пределы (пороги заданы в `global_policy.json`).
2. **Решение:** `RecoveryManager` создаёт `Proposal` типа `rollback`.
3. **Исполнение:** Используя `Version Graph` (см. [Memory_Hierarchy_Mem0g.md](../../01_Core_Architecture/Memory_Hierarchy_Mem0g.md)), система атомарно заменяет проблемный модуль на предыдущего champion.
4. **Карантин:** Проблемный геном помещается в `Quarantine Archive` с детальным логом причины отката.

Весь процесс занимает не более 10 секунд для некритичных модулей и не более 60 секунд для критических.

---

## 5. Интеграция с другими модулями

| Модуль | Характер связи |
| :--- | :--- |
| [Genetic_Engine.md](./Genetic_Engine.md) | Поставляет новых кандидатов (`challenger`), получает обратную связь о причинах отклонения для корректировки мутаций. |
| [Memory_Hierarchy_Mem0g.md](../../01_Core_Architecture/Memory_Hierarchy_Mem0g.md) | `Version Graph` хранит историю геномов и связей champion/challenger. L0 Meta‑Mem0g записывает результаты промоушенов и откатов для долгосрочного анализа. |
| [Validation_and_Verification.md](../../01_Core_Architecture/Validation_and_Verification.md) | Challenger проходит полный цикл детерминированной валидации, бенчмаркинга и хаос-тестов перед shadow-развёртыванием. |
| [Event_Bus_and_Artifact_Model.md](../../01_Core_Architecture/Event_Bus_and_Artifact_Model.md) | Все события `challenger_promoted`, `champion_rollback` и соответствующие артефакты публикуются в `EventBus`. |
| [Global_State_and_Decision_Pipeline.md](../../01_Core_Architecture/Global_State_and_Decision_Pipeline.md) | Решение о промоушене (HardState) проходит этап Governance с BFT-кворумом для критических модулей. |
| Доменный модуль `Economic_Autonomy` | PPO-исполнители развёртываются через Champion/Challenger. Их эффективность напрямую влияет на `ROI`. |

---

## 6. Конфигурация

Параметры модели задаются в `evolutiond.toml` и `global_policy.json`:

```toml
# evolutiond.toml (фрагмент)
[champion_challenger]
shadow_duration_sec = 3600          # минимальное время теневого теста (1 час)
promotion_quorum = 3               # количество Core Nodes для утверждения критического промоушена
rollback_threshold_errors = 10     # максимальное число ошибок за минуту до инициации отката
rollback_coherency_drop = 0.05     # падение когерентности, триггерящее откат
```

---

## 7. Связь с другими документами

· Генетический движок: Genetic_Engine.md
· Открытость эволюции: Open_Endedness.md
· Нейро-символьное управление: Neuro_Symbolic_Governance.md
· Принципы проектирования: Design_Principles.md
· Глоссарий: Glossary.md

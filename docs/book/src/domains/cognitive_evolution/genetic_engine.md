# Genetic Evolution Engine (Генетический движок эволюции)

**Назначение:** Реализовать непрерывный процесс самосовершенствования кода через популяционные методы, управляемые LLM мутации и многофакторную фитнес-функцию. Движок является основным поставщиком кандидатов для системы `Champion/Challenger` и ключевым механизмом достижения Open-Endedness в эволюции системы.

---

## 1. Архитектура движка

Движок реализован в виде сервиса **`evolutiond`** (Rust) и оперирует популяцией вариантов каждого критического модуля.

```

evolutiond/
├── population.rs      # управление популяцией, селекция, кроссовер
├── fitness.rs         # вычисление фитнеса (ссылается на Validation Pipeline)
├── llm_mutator.rs     # взаимодействие с DeepSeek-V4 (маска Vagrant)
├── diversity.rs       # Genetic Diversity Mandate
├── open_ended.rs      # детектор радикальных мутаций
├── stepping_stones.rs # Stepping Stone Archive и PFV-предиктор
├── telemetry.rs       # сохранение истории в sled
└── hot_reload.rs      # безопасная замена модулей

```

---

## 2. LLM-управляемая мутация

В отличие от случайных мутаций, `llm_mutator` получает на вход текущий код, телеметрию (историю дефектов, успешность) и генерирует новую версию, целенаправленно изменяя структуру. Для мутаций используется **DeepSeek‑V4 с ограниченной экспертной маской `Vagrant` (20% экспертов)**. Это снижает вычислительную нагрузку и предотвращает чрезмерно «креативные» изменения, способные дестабилизировать систему.

```rust
// evolutiond/src/llm_mutator.rs
pub async fn mutate_with_context(&self, code: &str, telemetry: &Telemetry) -> String {
    let prompt = format!(...);
    // Вызов DeepSeek-V4 с заголовком X-Species-Mask: vagrant
    self.deepseek_client.generate(&prompt, SpeciesMask::Vagrant).await
}
```

---

## 3. Фитнес-функция

Фитнес вычисляется как взвешенная сумма метрик. Базовая формула в Фазе 2:

```
Fitness = 0.25 * valid_score + 0.25 * perf_score + 0.2 * novelty + 0.3 * frontier_score
```

· valid_score ∈ {0, 1} — прошёл ли детерминированную валидацию.
· perf_score = 1 — benchmark_regression (чем меньше регрессия, тем выше).
· novelty — косинусное расстояние эмбеддингов кода до остальной популяции.
· frontier_score — оценка Architectus (60% экспертов) или локального предиктора.

Вес frontier_score может быть заменён на resilience_score при активном хаос-тестировании. Адаптивная фитнес-функция с байесовским взвешиванием описана в разделе 5 Cognitive_Evolution README.

---

## 4. Genetic Diversity Mandate (Мандат генетического разнообразия)

Назначение: Предотвратить вырождение популяции (mode collapse), когда все особи становятся вариациями одного успешного генома.

Diversity Score вычисляется как попарное среднее косинусное расстояние между эмбеддингами всех особей:

```
diversity = (2 / (N*(N-1))) * Σ_{i<j} (1 - cosine_similarity(emb_i, emb_j))
```

Пороги:

· warning (< 0.15): ↑ mutation_rate на 50%, ↑ вес novelty в фитнесе, активация NES.
· critical (< 0.08): Re-seeding из архива (2–3 старых генома с высоким diversity), принудительный NES на 10 поколений, сброс элитизма.

Все события diversity логируются в L0 Meta-Mem0g.

---

## 5. Open-Endedness Mandate (Стимулирование прорывных инноваций)

Система различает два типа мутаций:

· Incremental: Улучшение существующего кода в рамках той же парадигмы.
· Radical: Создание новой абстракции, меняющей способ решения задач (новый DSL, протокол консенсуса, альтернативная архитектура памяти).

Radical-мутации детектируются по созданию новых синтаксических конструкций (макросы, типажи), архитектурному сдвигу или наличию формального доказательства улучшения (Z3). За них начисляется radical_bonus (до +1.0 к фитнесу).

Периодически (раз в 30 дней или при стагнации diversity) запускается Meta-Innovation — выделение 20% ресурсов Core Node на решение «гранд-челленджа», выходящего за пределы текущих возможностей.

Детали — в Open_Endedness.md.

---

## 6. Stepping Stone Archive и PFV

Геномы, не прошедшие порог фитнеса для немедленного внедрения, но обладающие высокой новизной (novelty > 0.85) и структурной сложностью, сохраняются в Stepping Stone Archive (SSA). Для них вычисляется Potential Future Value (PFV) — предсказанная вероятность стать частью будущего прорыва.

· Модель PFV: легковесная нейросеть (Candle), обученная на исторических данных Innovation Archive.
· Использование: 20% особей новой популяции инициализируются случайными геномами из SSA; специальный оператор кроссовера с вероятностью 10% выбирает второго родителя из SSA.

Детали — в Open_Endedness.md.

---

## 7. Интеграция с циклом сна

Во время sleep_cycle_consolidation (см. Memory_Hierarchy_Mem0g) генетический движок запускает эволюцию для всех активных модулей. Лучшие геномы сохраняются в Mem0g L2 как «стратегии» и могут быть использованы для инициализации популяции при следующем пробуждении или на других узлах роя.

---

## 8. Конфигурация в evolutiond.toml

```toml
[population]
size = 10
elite_fraction = 0.25
crossover_rate = 0.7
mutation_rate = 0.3

[llm]
enabled = true
model = "deepseek-v4"
species_mask = "vagrant"
expert_percent = 20
context_size = 2048

[diversity]
enabled = true
warning_threshold = 0.15
critical_threshold = 0.08
check_interval_generations = 5
archive_size = 20

[open_endedness]
enabled = true
radical_bonus_max = 1.0

[stepping_stones]
enabled = true
novelty_threshold = 0.85
pfv_threshold = 0.3
archive_max_size = 500

[telemetry]
db_path = "/var/lib/swarm/evolution_db"
```

---

## 9. Интеграция с другими модулями

Модуль Характер связи
Champion_Challenger.md Поставляет новых challenger, получает обратную связь о причинах отклонения.
Open_Endedness.md Детектор радикальных мутаций, Innovation Archive, Meta-Innovation.
Neuro_Symbolic_Governance.md Формальная верификация новых DSL и протоколов, созданных radical-мутациями.
Memory_Hierarchy_Mem0g.md Хранение геномов и фитнес-истории в L2; L0 анализирует diversity и open-endedness.
Validation_and_Verification.md Вычисление valid_score и perf_score; бенчмаркинг и хаос-тесты.
Event_Bus_and_Artifact_Model.md Публикация новых геномов как артефактов code_snapshot.
Global_State_and_Decision_Pipeline.md Промоушен через Decision Pipeline (HardState для критических модулей).
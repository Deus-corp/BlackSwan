# Appendix O – Tooling for AST Integrity and Test-Driven Evolution (TDE)
## O.1. Общий принцип
Двухуровневый протокол TLSM (Two-Level Semantic Merge) требует специализированного инструментария, который гарантирует, что LLM никогда не пишет код в условиях семантической неопределённости. Вместо этого LLM используется только для генерации формальных требований (Conflict Invariants), а реальное разрешение конфликта происходит через детерминированное AST-слияние и эволюционный синтез.
Настоящее приложение описывает полный набор инструментов, необходимых для работы TLSM, их структуру, артефакты и команды запуска.
## O.2. Актуальный артефакт манифеста инструментов
Поле Значение
CID (IPFS) QmTLSMToolingManifestV2 (обновлённая версия)
BLAKE3 хеш (будет сгенерирован)
Имя файла tlsm_tooling_manifest.json
Версия 2.0 
```json
“ast_merger_crdt_bridge”: {
“cid”: “QmASTMergerCRDTBridgeV1”,
“type”: “library”,
“description”: “Rust-крейт, реализующий ASTFirstCRDTMerger для интеграции Strict AST Merge в CRDT-операции Mem0g.”
}
```
## O.3. Структура инструментария
### O.3.1. Уровень 1 – Strict AST Merge
**Название инструмента:** `ast_merger` (Rust)
**Назначение:** Детерминированное слияние AST-деревьев без участия LLM.
**Ключевые возможности:**
- Построение полного AST для BASE, OURS и THEIRS
- Обнаружение пересекающихся узлов
- Автоматическое слияние непересекающихся изменений
- Генерация структурированного отчёта о конфликтах
**Артефакт:** `QmASTMergerV1`
**Запуск:**
```bash
Ast_merger –base base.rs –ours ours.rs –theirs theirs.rs –output conflict_report.json
```
### O.3.2. Уровень 2 – Conflict Invariant Generator
**Название инструмента:** `invariant_generator` (Python + DeepSeek-V4 / Architectus
**Назначение:** Генерация минимального набора тестов-инвариантов, описывающих логику обеих конфликтующих веток.
**Строгие ограничения промпта:**
- LLM получает только сигнатуру функции, diff BASE→OURS и BASE→THEIRS.
- Запрещено генерировать реализацию кода.
- Требуется вывод только тестов (unit + property-based).
**Пример промпта (жёстко зафиксирован в артефакте):**
```text
You are a formal specification generator. 
Given the function signature and two diffs, generate ONLY tests that capture the intended behavior of BOTH changes.
Do NOT write any implementation code.
Return only valid pytest + hypothesis code.
```
**Артефакт:** `QmInvariantGeneratorV1`
### O.3.3. Evolutionary Synthesizer (интеграция с Genetic Engine)
Использует существующий `evolutiond` (раздел 6.5) в специальном режиме «Conflict Resolution».
Фитнес-функция переключается на формулу из раздела 6.5.9.
### O.3.4. Verification Pipeline
После синтеза новый патч проходит:
- Полный детерминированный пайплайн валидации (раздел 5.3)
- Semantic Integrity Guard (SIG)
- Z3-проверку L3-инвариантов
- Shadow benchmarking
## O.4. Полный workflow TLSM (MVP)
```mermaid
Graph TD
    A[Git/CRDT Conflict] à B[ast_merger L1]
    B à C{Пересечение AST?}
    C à|Нет| D[Автоматический мерж]
    C à|Да| E[invariant_generator L2]
    E à F[Генерация Conflict Invariants]
    F à G[Evolutionary Synthesis]
    G à H[Full Validation Pipeline]
    H à I{Success?}
    I à|Да| J[Commit to Main Trunk]
    I à|Нет| K[Rollback + Archive to Conflict Nodes]
```
## O.5. Команды для ручного запуска (отладка)
```bash
# 1. Запуск L1
Ast_merger –base main.rs –ours feature-a.rs –theirs feature-b.rs –report conflict.json
# 2. Запуск генератора инвариантов
Invariant_generator –conflict-report conflict.json –output invariants_test.py
# 3. Запуск эволюционного синтеза
Evolutiond –mode conflict-resolution –invariants invariants_test.py –module roi_dispatcher
```
## O.6. Связь с другими разделами
· **5.14.4** – Conflict-to-Test Transformation (Phase 1)  
· **6.5.9** – Conflict Resolution Fitness Mode (Phase 2)  
· **7.3.2** – TLSM Protocol (Phase 3)  
· **5.3** – Deterministic Validation Pipeline  
· **5.13.1** – Error Taxonomy  
· **Appendix I** – Formal Verification with Z3
## O.7. История изменений
| Версия | Дата       | Изменения                                      | CID                          |
|--------|------------|------------------------------------------------|------------------------------|
| V1     | 2026-04-20 | Первоначальная версия TLSM tooling             | QmTLSMToolingManifestV1      |
## O.8. Интеграция с CRDT Mem0g — ASTFirstCRDTMerger
Для бесшовного применения Strict AST Merge в операциях CRDT-слияния разработан специализированный крейт ast_merger_crdt_bridge. Он предоставляет асинхронный трейт CRDTMerge, который используется компонентом Mem0g при синхронизации узлов графа знаний.
Артефакт крейта:
· CID: QmASTMergerCRDTBridgeV1
· Имя: ast_merger_crdt_bridge-0.1.0.tar.gz
· Зависимости: ast_merger (Appendix O), tokio, serde_json.
Пример использования в Rust:
```rust
Use ast_merger_crdt_bridge::{ASTFirstCRDTMerger, CRDTMerge};
#[tokio::main]
Async fn main() {
Let merger = ASTFirstCRDTMerger::new(
AstMerger::default(),
Some(LLMFallback::new(“deepseek-v4”, SpeciesMask::Architectus))
);
Let base = KnowledgeNode::load(“QmBaseCode”).await?;
Let incoming = KnowledgeNode::load(“QmIncomingCode”).await?;
Match merger.merge(&base, &incoming).await? {
MergeResult::Merged(cid) => println!(“Success: {}”, cid),
MergeResult::MergedWithConflictNode(cid) => println!(“Resolved with conflict: {}”, cid),
MergeResult::ConflictNodeCreated(node) => println!(“Conflict node created: {}”, node.id),
}
}
```
Интеграция в Python-часть Mem0g:
Через PyO3/maturin крейт экспортируется как Python-модуль mem0g_crdt. Вызов осуществляется из sleep_cycle_consolidation при обработке накопленных изменений.
Конфигурация в global_policy.json:
```json
{
“crdt_merge_policy”: {
“strict_ast_first”: true,
“llm_fallback_enabled”: true,
“max_conflict_depth”: 5
}
}
```
## O.9. Continuous Semantic Fuzzing — автоматическая генерация тестов из AST‑изменений
### O.9.1. Назначение
TLSM гарантирует, что слияние кода не нарушает существующие инварианты,
Но не проверяет, что **новый код корректно обрабатывает все крайние
Случаи, специфичные для внесённых изменений**. Continuous Semantic
Fuzzing восполняет этот пробел: на основе AST‑диффа автоматически
Генерируются **мутационные тесты** (фаззинг‑входы), которые проверяют
Поведение изменённых функций на граничных и неожиданных значениях.
### O.9.2. Интеграция в TLSM (Уровень 1.5)
Расширенный пайплайн TLSM:
```
Конфликт при AST‑слиянии (Уровень 1)
│
▼

│ 1.5. Semantic Fuzzing│
│- Анализ изменённых AST‑узлов│
│- Генерация мутационных входов│
│(на основе типов, диапазонов,│
│структур)│
│- Запуск на BASE‑версии (должны │
│проходить) и на слитой версии│

│

Все тесты OKНайдены расхождения

▼▼
Переход кОтклонение слияния
Уровню 2или доработка
(LLM-инварианты)
```
### O.9.3. Алгоритм генерации мутационных тестов
**Вход:** AST‑дифф между BASE и сливаемыми ветками (OURS, THEIRS).
**Шаги:**
1. **Извлечение затронутых функций и их сигнатур.**
- Для каждой изменённой функции определяются типы аргументов,
Возвращаемого значения, используемые структуры.
2. **Генерация стратегий мутации.**
- Для примитивных типов (`int`, `float`): граничные значения (0, -1,
MAX, MIN, NaN, INF).
- Для строк: пустая, очень длинная, с нулевым байтом, с не‑UTF8
Последовательностями.
- Для коллекций: пустая, одноэлементная, огромная.
- Для пользовательских типов: значения полей по умолчанию,
Рекурсивно сгенерированные по тем же правилам.
3. **Генерация конкретных тестовых векторов.**
- Используется комбинаторный подход (pairwise testing) для покрытия
Взаимодействия параметров.
- Для функций с побочными эффектами (I/O, работа с памятью)
Генерируются последовательности вызовов.
4. **Запуск в изолированной среде (Shadow Sandbox).**
- Сравниваются результаты выполнения на BASE‑версии и на кандидате
Слияния.
- Любое расхождение (паника, разные возвращаемые значения, утечка
Памяти) — сигнал к отклонению слияния.
### O.9.4. Псевдокод генератора фазз‑тестов
```python
# ast_fuzzer/semantic_fuzzer.py
Import ast
Import itertools
From hypothesis import strategies as st
Class ASTSemanticFuzzer:
Def generate_tests(self, base_ast, merged_ast, functions_diff):
Tests = []
For func_name, changes in functions_diff.items():
Sig = extract_signature(base_ast, func_name)
Strat = self._build_strategy(sig)
# Генерация граничных и случайных значений
For _ in range(100):# Количество тестов на функцию
Args = strat.example()
Tests.append({
'function': func_name,
'args': args,
'expected': evaluate_on_base(base_ast, func_name, args)
})
Return tests
Def _build_strategy(self, signature):
Strategies = []
For param_type in signature.parameters:
If param_type == 'int':
Strategies.append(st.integers())
Elif param_type == 'float':
Strategies.append(st.floats(allow_nan=False, allow_infinity=False))
Elif param_type == 'str':
Strategies.append(st.text())
Elif param_type.startswith('List'):
Inner = self._build_strategy_for(param_type[5:-1])
Strategies.append(st.lists(inner, max_size=100))
Else:
Strategies.append(st.none())# fallback
Return st.tuples(*strategies)
```
### O.9.5. Интеграция с существующими инструментами
Инструмент Роль
Ast_merger Предоставляет AST‑дифф и список затронутых функций.
Hypothesis Используется как бэкенд для генерации стратегий и минимизации контрпримеров.
Shadow Sandbox Изолированное выполнение сгенерированных тестов.
Mem0g L2 Сохраняет успешные тесты как RegressionTest для будущих проверок.
O.9.6. Критерии активации и параметры
Активация:
· Всегда включён для конфликтных слияний (Уровень 1.5).
· Опционально может запускаться для обычных CRDT‑слияний с низкой
Quality_score.
Параметры в global_policy.json:
```json
{
«tlsm»: {
«semantic_fuzzing»: {
«enabled»: true,
«max_tests_per_function»: 100,
«timeout_sec»: 60
}
}
}
```
### O.9.7. Критерии успеха
Метрика Целевое значение
Обнаружено скрытых дефектов, пропущенных регрессиями ≥ 1 в месяц на активной кодовой базе
Ложных срабатываний (расхождение из‑за недетерминизма) ≤ 5%
Время фаззинга на одно слияние ≤ 60 секунд

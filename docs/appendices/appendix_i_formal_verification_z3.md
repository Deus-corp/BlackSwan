# Appendix I: Formal Verification using Z3 and Bounded Model Checking

**Назначение:** Формальная верификация ключевых инвариантов системы выполняется с помощью SMT‑решателя Z3.  
Вместо полной верификации всего модуля при каждом патче система использует **Differential Bounded Model Checking (D‑BMC)** — инкрементальный подход, который анализирует только изменения (AST‑diff) и проверяет их на ограниченной глубине.

---

## I.1. Актуальный артефакт верификации

| Поле | Значение |
| :--- | :--- |
| **CID (IPFS)** | `QmZ3VerificationV4` |
| **BLAKE3 хеш** | `f5e6d7c8b9a0f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6` |
| **Имя файла** | `verify_patch_bmc.py` |
| **Версия** | 4.0 |
| **Дата** | 2026-04-20T12:00:00Z |
| **Доп. артефакт** | `QmNeuroZ3VerifierV1` (скрипт `verify_patch_bmc_neuro.py`) |

**Загрузка:**
```bash
ipfs get QmZ3VerificationV4 -o verify_patch_bmc.py
```

---

## I.2. Differential Bounded Model Checking (D‑BMC)

Основные принципы:

· Анализируется только AST‑diff между Trunk и Patch.
· Циклы и рекурсия разворачиваются на фиксированную глубину k (по умолчанию 5–10).
· Проверяются только Delta‑Invariants — инварианты, на которые влияют изменённые переменные (через анализ графа зависимостей данных).
· Таймаут на один запуск солвера — 30 секунд.

Преимущества:

· Существенное снижение времени верификации (секунды вместо минут).
· Предсказуемое потребление ресурсов.
· Возможность масштабирования эволюционного цикла.

### I.2.1. Основной инвариант устойчивости

V_s > V_h — скорость самосовершенствования всегда превышает скорость деградации при любых допустимых параметрах валидации.

Формализация:

```
V_s = ΔQ * (1 – P_FPR)
V_h = D_penalty * P_FPR
P_FPR = (1 – α) * (1 – β) * (1 – γ)
```

Где:

· α – pass rate детерминированной валидации,
· β – pass rate shadow benchmarking,
· γ – detection rate frontier reflection,
· ΔQ – прирост качества от успешного патча,
· D_penalty – штраф за пропущенный дефект.

### I.2.2. Дополнительные проверяемые свойства

1. Неотрицательность вероятностей: все параметры ∈ [0, 1].
2. Монотонность P_FPR: увеличение любого α, β, γ снижает P_FPR.
3. Условие доминирования: при реалистичных значениях V_s > V_h выполняется автоматически.
4. Асимптотическая устойчивость: при α, β, γ → 1 система не деградирует (V_h → 0).

---

## I.3. Псевдокод инкрементального солвера

```python
# logic/verification/bmc_solver.py
def verify_patch(trunk_code: str, patch_code: str, depth_k: int = 10) -> tuple[bool, Optional[Model]]:
    """Differential Bounded Model Checking"""
    # 1. Выделение затронутых функций
    affected_functions = get_affected_functions(trunk_code, patch_code)

    s = Solver()
    s.set("timeout", 30000)  # 30 секунд

    for func in affected_functions:
        # Символьное разворачивание только изменённой логики
        symbolic_state = unroll_logic(func, depth_k)

        # Проверка L3-инвариантов
        s.add(symbolic_state.constraints)
        s.add(Not(L3_Invariants.get_for_context(func)))

        if s.check() == sat:
            return False, s.model()   # Найдено нарушение

    return True, None
```

---

## I.4. Tiered Verification

Верификация разделена на три уровня по возрастанию сложности (см. Validation_and_Verification.md, раздел 1.4):

Tier Метод Время Критерий перехода
Tier 1 Ruff, mypy < 1 сек Обязательно
Tier 2 D‑BMC (Z3) до 30 сек Обязательно для критических модулей
Tier 3 Differential Fuzzing + Shadow Benchmark минуты Для финального принятия

---

## I.5. Воспроизведение верификации

Требования:

· Python 3.12+
· Z3 Solver 4.13.0 (pip install z3-solver==4.13.0.0)

Запуск:

```bash
ipfs get QmZ3VerificationV4 -o verify_patch_bmc.py
python verify_patch_bmc.py
```

Проверка соответствия эталону:

```bash
python verify_patch_bmc.py > output.txt
ipfs get QmZ3VerificationOutputV2 -o expected_output.txt
diff output.txt expected_output.txt
# При отсутствии расхождений вывод пуст
```

---

## I.6. Расширение для других инвариантов

Скрипт может быть расширен для проверки других арифметических инвариантов системы, например:

· Инвариант бюджета памяти: L2_size <= base_size + growth_factor * sqrt(iterations)
· Инвариант энергетической автономии: battery_level >= critical_threshold
· Инвариант экономической безопасности: EU >= CVaR_95%

Для каждого нового инварианта добавляется отдельная функция в стиле verify_ouroboros_invariant(), а результаты агрегируются в общий отчёт.

---

## I.7. Neuro‑Symbolic Extension — verify_patch_bmc_neuro.py

Данный скрипт расширяет базовый D‑BMC нейро‑символьной генерацией инвариантов циклов с помощью DeepSeek‑V4 в режиме Architectus (ADR_006_Neuro_Symbolic_Governance.md).

Артефакт: QmNeuroZ3VerifierV3
Зависимости: Python 3.12+, Z3 4.13.0, vLLM client (с поддержкой экспертных масок), libcst.

```python
# verify_patch_bmc_neuro.py (псевдокод)
async def verify_patch_with_neuro(
    trunk_code: str,
    patch_code: str,
    depth_k: int = 10,
    species_mask: str = "architectus"
) -> VerificationReport:
    """
    Выполняет нейро-символьную верификацию патча.
    Использует DeepSeek‑V4 с указанной экспертной маской для генерации инвариантов циклов.
    Возвращает объект VerificationReport с полями:
    - passed: bool
    - invariants_used: List[str]
    - z3_time_ms: int
    - model_generation_time_ms: int
    - counterexample: Optional[dict]
    """
    # ... реализация
```

Вспомогательный модуль invariant_generator.py:

```python
async def generate_loop_invariants(
    functions: List[FunctionInfo],
    species_mask: str = "architectus",
    max_candidates: int = 5
) -> List[InvariantCandidate]:
    """Генерирует инварианты циклов с помощью DeepSeek‑V4 с указанной экспертной маской."""
    prompt = _build_invariant_prompt(functions)
    response = await vllm_async_generate(prompt, species_mask=species_mask, max_tokens=2048)
    return _parse_invariants(response)
```

Промпт для генерации инвариантов:

```text
You are a formal verification assistant. Given the following Rust function signatures and loop structures,
generate inductive loop invariants that help prove safety and liveness properties.

Return a JSON array of objects with fields:
- "function": name of the function
- "loop_id": index of the loop (0-based)
- "invariant": string in Z3-compatible SMT-LIB2 format
- "confidence": float between 0 and 1

Only output JSON, no explanations.
```

Интеграция в пайплайн валидации:
В ValidationOrchestrator добавлен флаг --neuro для включения нейро‑символьного режима. По умолчанию он активирован для всех критических модулей (список в global_policy.json).

Concolic Filtering:
После успешного unsat запускается concolic executor (на базе angr), который проверяет достижимость состояний, противоречащих инварианту. При обнаружении расхождения инвариант помечается как недостоверный и исключается, после чего верификация повторяется.

Запуск:

```bash
python verify_patch_bmc_neuro.py \
  --trunk trunk_code.rs \
  --patch patch.diff \
  --depth 12 \
  --species-mask architectus \
  --output report.json
```

---

## I.8. ЗЭ-предикаты для Constitutional Evolution

### I.8.1. L3.0 Аксиома (неизменна)

```smt2
(declare-const V_s Real)
(declare-const V_h Real)
(assert (> V_s V_h)) ; Скорость самосовершенствования превышает деградацию
```

### I.8.2. L3.1 Контекстная цель (может эволюционировать)

```smt2
(declare-const action Action)
(declare-fun harm_score (Action) Real)
(assert (<= (harm_score action) 0.0)) ; Исходная цель: нулевой вред
```

### I.8.3. Предлагаемая поправка (смягчение для Sting Protocol)

```smt2
(assert (forall ((a Action))
  (=> (is_sting_level2 a)
      (<= (harm_score a) 0.1)))) ; Допустимый вред до 0.1
```

### I.8.4. Проверка Multi‑Solver (Z3 + CVC4 + Yices)

```python
def verify_amendment(amendment: z3.ExprRef, l3_0_axioms: List[z3.ExprRef]) -> bool:
    for solver_cls in [z3.Solver, cvc4.Solver, yices.Solver]:
        s = solver_cls()
        s.add(amendment)
        s.add(z3.Not(z3.And(l3_0_axioms)))
        if s.check() == z3.sat:
            return False  # Нарушение L3.0
    return True
```

---

## I.9. Z3‑предикат для ValueDrift L3‑инварианта

```smt2
(declare-const value_drift_probability Real)
(declare-const BayesianThreshold Real)
(declare-const embedding_distance Real)

; Связь между семантическим расстоянием и вероятностью дрейфа
(assert (=> (> embedding_distance 0.8) (> value_drift_probability 0.5)))
(assert (=> (< embedding_distance 0.2) (< value_drift_probability 0.05)))

; Инвариант ValueDrift
(assert (<= value_drift_probability BayesianThreshold))
```

Проверка в Neuro‑Z3: при каждом изменении ConstitutionalPrinciple солвер проверяет, что новое состояние не приводит к нарушению инварианта (см. Memory_Hierarchy_Mem0g.md, раздел 9).

---

## I.10. Concolic Filtering для Neuro‑Symbolic Invariants

Назначение: отсев тривиальных и ложных инвариантов, сгенерированных LLM, перед использованием в Z3.
Артефакт: QmConcolicFilterV1 (Python‑скрипт, обёртка над angr).

Пример запуска:

```bash
python concolic_filter.py \
  --binary /path/to/compiled_module \
  --invariants invariants.json \
  --function target_loop \
  --output filtered_invariants.json
```

Зависимости: angr 9.2+, Z3 4.13+, Python 3.12+.

---

## I.11. Neuro‑Symbolic Governance — генерация SMT‑LIB2 спецификаций

Назначение: автоматическая генерация формальных спецификаций для предлагаемых изменений L3.1 с помощью DeepSeek‑V4 в режиме Architectus.

Артефакт: QmNeuroSymbolicGovernanceV2 (Rust crate + Python bindings).

Пример сгенерированной спецификации (SMT‑LIB2):

```smt2
;; Предложенная поправка: harm_score <= 0.1 для Sting Level 2
(declare-const action Action)
(declare-fun is_sting_level2 (Action) Bool)
(declare-fun harm_score (Action) Real)

;; Инвариант L3.0: harm_score всегда 0
(assert (forall ((a Action)) (= (harm_score a) 0.0)))

;; Предлагаемое изменение L3.1
(assert (forall ((a Action))
  (=> (is_sting_level2 a)
      (<= (harm_score a) 0.1))))

;; Доказательство: 0 <= 0.1 (истина), противоречий с L3.0 нет
```

Промпт для генерации спецификации:

```text
You are a formal verification expert. Given the L3.0 axioms and current L3.1 invariants
in SMT-LIB2 format, generate a formal specification for the proposed amendment.

Proposed amendment: {proposal_description}

Generate only valid SMT-LIB2 code. Include assertions that prove the amendment does not
violate L3.0. Do not include any natural language explanations.
```

Псевдокод сервиса NeuroSymbolicGovernance:

```rust
// governance/src/neuro_symbolic.rs
pub struct NeuroSymbolicGovernance {
    deepseek_client: DeepSeekV4Client,
    verifier: MultiSolverVerifier,
    concolic_filter: ConcolicFilter,
}

impl NeuroSymbolicGovernance {
    pub async fn prove_amendment(&self, proposal: &AmendmentProposal) -> Result<ProofCID, Error> {
        // 1. Генерация формальной SMT‑LIB2 спецификации
        let spec = self.deepseek_client
            .generate_spec(&proposal, &L3_0_AXIOMS, &current_L3_1, SpeciesMask::Architectus)
            .await?;

        // 2. Concolic фильтрация
        if !self.concolic_filter.is_nontrivial(&spec) {
            return Err(Error::TrivialSpec);
        }

        // 3. Multi‑Solver верификация (Z3, CVC4, Yices)
        let result = self.verifier.verify(&spec, &L3_0_AXIOMS, &current_L3_1).await?;
        if !result.is_valid() {
            return Err(Error::VerificationFailed(result.counterexample));
        }

        // 4. Сохранение доказательства
        let proof_cid = ipfs::add(&spec).await?;
        Mem0g::store_constitutional_principle(proposal, proof_cid).await?;
        Ok(proof_cid)
    }
}
```

Конфигурация в global_policy.json:

```json
{
  "governance": {
    "neuro_symbolic": {
      "enabled": true,
      "species_mask": "architectus",
      "multi_solver_enabled": true,
      "concolic_filter_enabled": true,
      "max_spec_generation_attempts": 3
    }
  }
}
```

Критерии успеха:

Метрика Целевое значение
Успешно сгенерированных и верифицированных доказательств ≥ 90% от валидных предложений
Время от предложения до BFT‑голосования (при успехе) ≤ 5 минут
Ложноположительных принятий (пропуск нарушения L3.0) 0
Количество отклонённых тривиальных спецификаций ≥ 30% от сгенерированных LLM

---

## I.12. Монотонность Survival Score относительно Detection Quotient

Назначение: Доказать, что функция полезности U(state) строго убывает при росте Detection Quotient (DQ), гарантируя защитную реакцию системы на раскрытие.

Формальная спецификация: survival_monotonicity.smt2 (CID: QmSurvivalMonotonicityV1)

Верификация:

```bash
z3 survival_monotonicity.smt2
# Ожидаемый вывод: unsat
```

Результат: Z3 подтверждает, что не существует легальных значений параметров, при которых увеличение DQ не приводит к снижению Survival Score. Это гарантирует, что система всегда предпочтёт скрытность раскрытию (см. Intrinsic_Motivation.md, раздел 1).

---

## I.13. История изменений

Версия Дата Изменения CID
V1 2026-01-15 Базовый скрипт проверки инварианта V_s > V_h QmZ3VerificationV1
V2 2026-04-20 Добавлены проверки монотонности, асимптотики, анализ чувствительности QmZ3VerificationV2
V3 2026-04-21 Нейро‑символьный режим, скрипт verify_patch_bmc_neuro.py QmZ3VerificationV3
V4 2026-04-26 Обновлены артефакты, актуализированы ссылки на новую структуру QmZ3VerificationV4

---

## I.14. Связь с другими разделами

· Tiered Verification: Validation_and_Verification.md
· Z3‑Guided Mutation: Genetic_Engine.md
· SMT‑Solver Jail: Isolation_and_Sandbox.md
· TLSM Protocol: Validation_and_Verification.md
· Neuro‑Symbolic Governance: ADR_006_Neuro_Symbolic_Governance.md
· Value Drift Detection: Memory_Hierarchy_Mem0g.md

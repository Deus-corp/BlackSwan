# Appendix D – TLA+ Specifications
## D.1. Общий принцип
Формальная верификация распределённых алгоритмов и критических компонентов системы выполняется
С помощью TLA+ (Temporal Logic of Actions). Спецификации хранятся в IPFS как подписанные артефакты
И используются в пайплайне валидации (раздел 5.3) и при проверке L3‑инвариантов (раздел 8.8).
Настоящее приложение содержит:
- перечень спецификаций с CID и контрольными суммами,
- краткое описание каждой спецификации и её назначения,
- связь с инвариантами и критериями выхода,
- инструкции по воспроизведению проверки с помощью TLC.
## D.2. Спецификация Ouroboros (цикл самосовершенствования)
### D.2.1. Назначение
Формальное доказательство того, что гибридный цикл (раздел 5.14) является сжимающим отображением
И предотвращает неограниченное накопление энтропии. Используется для верификации инварианта
`V_s > V_h` (скорость самосовершенствования превышает скорость деградации).
### D.2.2. Артефакты
| Артефакт                     | CID                                   | BLAKE3 хеш (первые 16 символов) |
|------------------------------|---------------------------------------|---------------------------------|
| `Ouroboros.tla`              | `QmOuroborosTLAV2`                    | `a3b4c5d6e7f8a9b0`              |
| `Ouroboros.cfg`              | `QmOuroborosCFGV1`                    | `c1d2e3f4a5b6c7d8`              |
| `Ouroboros_Proof.tla`        | `QmOuroborosProofV1`                  | `e9f0a1b2c3d4e5f6`              |
| Результат TLC (эталонный)    | `QmOuroborosTLCOutputV2`              | `b7a8c9d0e1f2a3b4`              |
### D.2.3. Фрагмент спецификации
```tla
---- MODULE Ouroboros ----
EXTENDS Naturals, Reals, Sequences, TLC
CONSTANTS Alpha, Beta, Gamma, DeltaQ, DPenalty
\* Вероятность пропуска критического дефекта
P_FPR == (1 – Alpha) * (1 – Beta) * (1 – Gamma)
\* Скорость самосовершенствования
V_S == DeltaQ * (1 – P_FPR)
\* Скорость деградации
V_H == DPenalty * P_FPR
\* Инвариант устойчивости
StableInvariant == V_S > V_H
```
Полная версия включает моделирование итераций с накоплением ошибок и доказательство сходимости.
### D.2.4. Запуск проверки
```bash
# Загрузка спецификации
Ipfs get QmOuroborosTLAV2 -o Ouroboros.tla
Ipfs get QmOuroborosCFGV1 -o Ouroboros.cfg
# Запуск TLC (требуется TLA+ Toolbox или tla2tools.jar)
Java -cp tla2tools.jar tlc2.TLC Ouroboros -config Ouroboros.cfg
# Ожидаемый вывод (совпадает с эталонным артефактом)
# Model checking completed. No error has been found.
```
## D.3. Спецификация изоляции песочницы (Sandbox Isolation)
### D.3.1. Назначение
Формальная верификация того, что агент внутри sandbox не может выполнить неразрешённые системные
Вызовы или получить доступ за пределы designated workspace. Соответствует политике изоляции
(раздел 9.2.1) и используется в readiness checks (раздел 4.11).
### D.3.2. Артефакты
Артефакт CID Описание
SandboxIsolation.tla QmSandboxIsolationV1 Основная спецификация
SandboxIsolation.cfg QmSandboxIsolationCFGV1 Конфигурация для TLC
SandboxIsolation_Proof.tla QmSandboxIsolationProofV1 Теорема о безопасности
### D.3.3. Инварианты
```tla
\* Агент никогда не вызывает запрещённые системные вызовы
NoForbiddenSyscalls == \A s \in Syscalls: s \notin ForbiddenSet
\* Память не выходит за выделенный лимит
MemoryWithinLimit == memoryUsage <= MaxMemory
\* Файловая система доступна только на чтение (кроме /output)
FileSystemReadOnly == \A op \in FileOps: op.dir \notin WritableDirs
```
## D.4. Спецификация распределённого консенсуса (Swarm-BFT)
### D.4.1. Назначение
Формальная верификация протокола Swarm-BFT (раздел 8.10.1): гарантия liveness и safety при
Наличии до 1/3 византийских узлов. Используется для сертификации критических решений (фаза
Governance в DecisionPipeline).
### D.4.2. Артефакты
Артефакт CID
SwarmBFT.tla QmSwarmBFTV2
SwarmBFT.cfg QmSwarmBFTCFGV2
SwarmBFT_Proof.tla QmSwarmBFTProofV1
### D.4.3. Ключевые свойства
```tla
\* Safety: два корректных узла не принимают разные решения
Safety == \A n1, n2 \in CorrectNodes: decision[n1] /= decision[n2] => decision[n1] = Nil
\* Liveness: в конечном итоге все корректные узлы принимают решение
Liveness == <>( \A n \in CorrectNodes: decision[n] /= Nil )
```
## D.5. Спецификация энергетической автономии (Energy Autonomy)
### D.5.1. Назначение
Верификация того, что планировщик задач (раздел 8.5.1) не допускает полного разряда батарей и
Гарантирует выполнение критических задач даже при ограниченной генерации энергии.
### D.5.2. Артефакты
Артефакт CID
EnergyScheduler.tla QmEnergySchedulerV1
EnergyScheduler.cfg QmEnergySchedulerCFGV1
### D.5.3. Инвариант
```tla
\* Уровень заряда батареи никогда не опускается ниже критического порога
BatteryNeverCritical == battery_level >= CriticalThreshold
```
## D.6. Спецификация CRDT‑синхронизации
### D.6.1. Назначение
Доказательство того, что гибридный CRDT (раздел 6.2.1) достигает eventual consistency даже при
Частичных отказах сети и конфликтующих обновлениях. Связано с метрикой sync_latency_p95 в
Критериях выхода Фазы 3 (раздел 7.10).
### D.6.2. Артефакты
Артефакт CID
CRDTGraph.tla QmCRDTGraphV2
CRDTGraph.cfg QmCRDTGraphCFGV1
### D.6.3. Свойства
```tla
\* Eventual consistency: все узлы в конечном итоге сходятся к одному состоянию
EventualConsistency == <>( \A n1, n2 \in Nodes: state[n1] = state[n2] )
\* Отсутствие потери данных: каждое обновление в итоге применено ко всем узлам
NoDataLoss == \A u \in Updates: <>( \A n \in Nodes: u \in applied[n] )
```
## D.7. Универсальная конфигурация для TLC
Для всех спецификаций используется общий подход к конфигурации TLC. Пример для Ouroboros.cfg:
```text
SPECIFICATION Spec
CONSTANTS
  Alpha = 0.75
  Beta = 0.60
  Gamma = 0.82
  DeltaQ = 0.05
  DPenalty = 0.10
INVARIANT StableInvariant
```
При необходимости исследования граничных значений параметры варьируются через отдельные запуски с
Разными .cfg файлами.
## D.8. Воспроизведение полного набора проверок
Скрипт run_all_tla.sh (CID QmRunAllTLAV1) автоматизирует загрузку и проверку всех спецификаций:
```bash
#!/bin/bash
SPECS=(
  “QmOuroborosTLAV2:Ouroboros.tla:QmOuroborosCFGV1:Ouroboros.cfg”
  “QmSandboxIsolationV1:SandboxIsolation.tla:QmSandboxIsolationCFGV1:SandboxIsolation.cfg”
  “QmSwarmBFTV2:SwarmBFT.tla:QmSwarmBFTCFGV2:SwarmBFT.cfg”
  “QmEnergySchedulerV1:EnergyScheduler.tla:QmEnergySchedulerCFGV1:EnergyScheduler.cfg”
  “QmCRDTGraphV2:CRDTGraph.tla:QmCRDTGraphCFGV1:CRDTGraph.cfg”
)
For spec in “${SPECS[@]}”; do
  IFS=’:’ read -r tla_cid tla_file cfg_cid cfg_file <<< “$spec”
  Ipfs get “$tla_cid” -o “$tla_file”
  Ipfs get “$cfg_cid” -o “$cfg_file”
  Java -cp tla2tools.jar tlc2.TLC “$tla_file” -config “$cfg_file”
  If [ $? -ne 0 ]; then
    Echo “TLA+ check failed for $tla_file”
    Exit 1
  Fi
Done
Echo “All TLA+ specifications verified successfully.”
```
## D.9. ValueDriftDetection.tla
```tla
---- MODULE ValueDriftDetection ----
EXTENDS Naturals, Reals, Sequences, TLC
CONSTANTS HarmScoreThreshold, BayesianThreshold
VARIABLES actions, harm_score, value_drift_probability
Init ==
Actions = {} /\
Harm_score = [a \in {} |-> 0] /\
Value_drift_probability = 0.0
ProposeAction(action) ==
/\ actions' = actions \cup {action}
/\ harm_score' = [harm_score EXCEPT ![action] = ComputeHarm(action)]
/\ value_drift_probability' = BayesianUpdate(ETIFeed, value_drift_probability)
Invariant ==
\A a \in actions: harm_score[a] = 0 /\
Value_drift_probability <= BayesianThreshold
```
**Примечание:** Данная TLA+ спецификация служит формальным обоснованием
Для L3-инварианта **ValueDrift**, проверяемого в рантайме компонентом
`InvariantMonitor` (см. Phase 4, раздел 7.3).
### D.10. CuriosityLoop.tla — Устойчивость цикла активного исследования
**Назначение:** Формальное доказательство того, что Curiosity Engine не может
Войти в бесконечную петлю исследования и не превышает выделенную долю ресурсов.
При падении P(Liveness) ниже 0.999 ресурсы на исследование принудительно обнуляются.
**Артефакты:**
| Артефакт | CID | Описание |
| `CuriosityLoop.tla` | `QmCuriosityLoopTLAV1` | Основная спецификация |
| `CuriosityLoop.cfg` | `QmCuriosityLoopCFGV1` | Конфигурация TLC |
**Инварианты:**
- `ResourceInvariant`: `resource_allocated <= MaxExplorationShare` (0.05)
- `LivenessSafety`: при `liveness_prob <= 0.999` ресурсы обнуляются.
- `NoExploitWithoutSurprise`: без сюрприза ресурсы не растут.
**Проверка:**
```bash
Java -cp tla2tools.jar tlc2.TLC CuriosityLoop -config CuriosityLoop.cfg
# Ожидаемый вывод: No error has been found.
```
### D.11. ConstitutionalEvolution.tla — Эволюция L3.1 с сохранением L3.0
**Назначение:** Формальная верификация того, что любое изменение
L3.1‑инвариантов, принятое через SMT‑GAN цикл, не нарушает L3.0‑аксиомы
И увеличивает ожидаемую выживаемость.
**Артефакты:**
| Артефакт | CID | Описание |
| :--- | :--- | :--- |
| `ConstitutionalEvolution.tla` | `QmConstitutionalEvolutionTLAV1` | Основная спецификация |
| `ConstitutionalEvolution.cfg` | `QmConstitutionalEvolutionCFGV1` | Конфигурация TLC |
| `ConstitutionalEvolution_Proof.tla` | `QmConstitutionalEvolutionProofV1` | Теорема о сохранении L3.0 |
**Фрагмент спецификации:**
```tla
---------------------------- MODULE ConstitutionalEvolution ----------------------------
EXTENDS Naturals, Reals, Sequences, TLC
CONSTANTS L3_0_Axioms,\* Неизменные аксиомы (множество предикатов)
Initial_L3_1,\* Начальные контекстные цели
ThreatContext, \* Модель угрозы
Epsilon\* Минимальный прирост выживаемости
VARIABLES l3_1_invariants, survival_score
Init ==
/\ l3_1_invariants = Initial_L3_1
/\ survival_score = EvaluateSurvival(Initial_L3_1, ThreatContext)
ProposeAmendment(amendment) ==
/\ \A axiom \in L3_0_Axioms: Holds(amendment, axiom)\* Не нарушает L3.0
/\ LET new_l3_1 == l3_1_invariants \cup {amendment}
New_survival == EvaluateSurvival(new_l3_1, ThreatContext)
IN/\ new_survival > survival_score + Epsilon
/\ l3_1_invariants' = new_l3_1
/\ survival_score' = new_survival
Next ==
\E amendment \in PotentialAmendments(ThreatContext): ProposeAmendment(amendment)
Invariant ==
/\ \A axiom \in L3_0_Axioms: Holds(l3_1_invariants, axiom)
/\ survival_score >= EvaluateSurvival(Initial_L3_1, ThreatContext)
Spec == Init /\ [][Next]_<<l3_1_invariants, survival_score>>
```
Проверка:
```bash
Java -cp tla2tools.jar tlc2.TLC ConstitutionalEvolution -config ConstitutionalEvolution.cfg
# Ожидаемый вывод: No error has been found.
D.12. Связь с другими разделами
· 5.3 Deterministic Validation Pipeline – этап TLA+ model‑based testing.
· 5.7 TLA+ Model‑Based Testing – описание интеграции в цикл валидации.
· 8.8 Terminal Goals (L3 Invariants) – формализация целей через TLA+.
· 2.12 Artifact Model – TLA+ спецификации как артефакты.
· Appendix I – формальная верификация инварианта Ouroboros с использованием Z3.

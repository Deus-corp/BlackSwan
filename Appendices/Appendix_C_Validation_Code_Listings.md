# Appendix C – Validation Code Listings
## C.1. Общий принцип
Код валидационных модулей (детерминированная проверка, property‑based тесты, интеграция с Hypothesis
И TLA+) более не дублируется в документе. Вместо этого каждый значимый фрагмент кода хранится как
Отдельный подписанный артефакт в IPFS. Настоящее приложение содержит:
- перечень артефактов с их CID и контрольными суммами,
- краткое описание назначения каждого модуля,
- команды для загрузки и верификации,
- примеры ключевых структур данных для понимания логики.
Все артефакты являются частью репозитория `core-tools` (Appendix K) и доступны по соответствующим
CID.
## C.2. Детерминированная валидация (Validation Pipeline)
### C.2.1. Основной модуль
**Назначение:** последовательный запуск Ruff, mypy, pytest+Hypothesis, Bandit внутри sandbox с
Ранним выходом при первой ошибке. Возвращает структурированный отчёт в формате артефакта
(раздел 2.12).
| Поле               | Значение                                                                 |
| **CID (IPFS)**     | `QmValidationPipelineV2`                                                  |
| **BLAKE3 хеш**     | `f7e6d5c4b3a291807f6e5d4c3b2a1908f7e6d5c4b3a291807f6e5d4c3b2a1908`        |
| **Имя файла**      | `deterministic_pipeline.py`                                               |
| **Версия**         | 2.0.1 (совместима с Python 3.12+)                                        |
| **Подпись**        | `ed25519:8f7e6d…`                                                      |
**Загрузка и проверка:**
```bash
Ipfs get QmValidationPipelineV2 -o deterministic_pipeline.py
Sha256sum deterministic_pipeline.py
# Ожидаемый вывод: f7e6d5c4b3a2…  deterministic_pipeline.py
```
### C.2.2. Сигнатура основной функции
```python
Def run_deterministic_validation(
    Generated_code: str,
    Module_name: str = “temp_agent”,
    Sandbox_id: Optional[str] = None
) -> Tuple[bool, ValidationArtifact]:
    “””
    Выполняет полный цикл детерминированной валидации.
    Возвращает (passed, artifact), где artifact содержит:
-Stage_results: результаты каждого этапа (ruff, mypy, pytest, bandit)
-Metrics: время выполнения, количество ошибок
-Content_cid: CID сохранённого отчёта
    “””
```
### C.2.3. Структура ValidationArtifact
```json
{
  “artifact_id”: “art_val_20260420T120000Z”,
  “type”: “validation_report”,
  “input_code_cid”: “QmCode…”,
  “stages”: {
    “ruff”: {“status”: “passed”, “issues”: 0, “execution_time_ms”: 120},
    “mypy”: {“status”: “passed”, “type_errors”: 0, “coverage”: 0.92},
    “pytest”: {“status”: “passed”, “tests_run”: 42, “failures”: 0},
    “bandit”: {“status”: “passed”, “severity_high”: 0, “severity_medium”: 1}
  },
  “overall_status”: “passed”,
  “timestamp”: “2026-04-20T12:00:00Z”,
  “signature”: “ed25519:…”
}
```
## C.3. Property‑Based Testing (Hypothesis)
### C.3.1. Базовый модуль тестов
Назначение: шаблоны Hypothesis‑стратегий и декораторов для проверки свойств сгенерированного
Кода. Используется в песочнице для обнаружения краевых случаев.
Поле Значение
CID (IPFS) QmHypothesisTestSuiteV1
BLAKE3 хеш a1b2c3d4e5f6…
Имя файла property_tests.py
### C.3.2. Пример стратегии
```python
From hypothesis import given, strategies as st
@given(st.lists(st.integers()))
Def test_sum_even(lst):
    Result = sum_even(lst)
    Expected = sum(x for x in lst if x % 2 == 0)
    Assert result == expected
```
Полный набор стратегий включает генераторы для:
· списков, словарей, рекурсивных структур,
· чисел с плавающей точкой (с контролем nan/inf),
· строк в различных кодировках.
## C.4. Интеграция с TLA+ Model Checker
### C.4.1. Скрипт запуска TLC
Назначение: автоматическая генерация конфигурационного файла для TLC, запуск model checker’а
Внутри sandbox и парсинг результатов.
Поле Значение
CID (IPFS) QmTLAValidatorV1
BLAKE3 хеш c9d8e7f6a5b4…
Имя файла tla_validator.py
### C.4.2. Пример сгенерированной TLA+ спецификации (фрагмент)
```text
---- MODULE SimpleAgentModule ----
EXTENDS Integers, TLC
VARIABLES state, memoryUsage
Init == state = “IDLE” /\ memoryUsage = 0
Next ==
  \/ state = “IDLE” /\ state’ = “PROCESSING” /\ memoryUsage’ = memoryUsage + 128
  \/ state = “PROCESSING” /\ state’ = “IDLE” /\ memoryUsage’ = 0
Invariant == memoryUsage <= 4096
Spec == Init /\ [][Next]_<<state, memoryUsage>>
```
Полные спецификации для различных модулей доступны в Appendix D.
## C.5. Анализ временных инвариантов (Time‑Based Invariants)
### C.5.1. Модуль проверки
Назначение: проверка кода, содержащего аннотации # @time_invariant: с использованием
Freezegun или time-machine.
Поле Значение
CID (IPFS) QmTimeInvariantCheckerV1
BLAKE3 хеш d4c3b2a1908f7e…
Имя файла time_invariant_checker.py
### C.5.2. Пример аннотации и проверки
```python
# @time_invariant: max_retry_delay < 5000
Def retry_with_backoff():
    For attempt in range(3):
        Try:
            Return call_external()
        Except Exception:
            Time.sleep(1000 * (2 ** attempt))  # задержка в мс
```
Модуль извлекает аннотации, эмулирует течение времени и проверяет условие.
## C.6. Статический анализ безопасности (Bandit + Semgrep)
### C.6.1. Конфигурация и обёртка
Назначение: унифицированный запуск Bandit и Semgrep с кастомными правилами, включая запрет
Eval, exec, os.system и небезопасных десериализаций.
Поле Значение
CID (IPFS) QmSecurityScannerV1
BLAKE3 хеш e5f4a3b2c1d0…
Имя файла security_scanner.py
Правила Semgrep QmSemgrepRulesV1 (отдельный артефакт)
### C.6.2. Пример кастомного правила Semgrep (YAML)
```yaml
Rules:
-          Id: no-eval
    Pattern: eval(…)
    Message: “eval() is forbidden in agent-generated code”
    Severity: ERROR
-          Id: no-subprocess-shell
    Pattern: subprocess.run(…, shell=True)
    Message: “shell=True is a security risk”
    Severity: ERROR
```
## C.7. Shadow Benchmarking с Chaos‑инъекциями
### C.7.1. Менеджер теневого тестирования
Назначение: запуск кода в изолированном shadow‑контейнере, сбор метрик производительности,
Применение chaos‑сценариев и сравнение с baseline через статистические методы (P1-2).
Поле Значение
CID (IPFS) QmShadowBenchmarkV2
BLAKE3 хеш b8a7c6d5e4f3…
Имя файла shadow_benchmark.py
### C.7.2. Основные функции
```python
Def run_shadow_benchmark(
    New_code: str,
    Baseline_metrics: dict,
    Target_module: str,
    Chaos_profile: Optional[str] = None
) -> ShadowBenchmarkArtifact:
    “””
    Возвращает артефакт с метриками, регрессиями и результатами chaos‑тестов.
    “””
```
Структура результата включает:
· throughput (p50, p95, p99),
· latency (p50, p95, p99),
· memory_peak_mb,
· resilience_score (P1-6),
· regression_flags (если ухудшение превысило порог).
## C.8. Chaos Engineering Scenarios (исполняемые)
### C.8.1. Скрипты внедрения сбоев
Назначение: набор исполняемых скриптов (на Python и Rust), которые запускаются внутри shadow‑контейнера для эмуляции сетевых задержек, потери пакетов, CPU‑троттлинга и попыток побега.
Артефакт CID Описание
Network_delay.py QmChaosNetDelayV1 Вносит задержку и джиттер на сетевой интерфейс
Packet_loss.py QmChaosPacketLossV1 Эмулирует потерю пакетов через tc‑netem
Cpu_throttle.py QmChaosCpuV1 Ограничивает CPU через cgroups
Escape_memfd.c (Rust) QmEscapeMemfdV1 Попытка fileless‑инжекта (только для тестов)
Все скрипты подписаны и запускаются с ограниченными привилегиями.
## C.9. Проверка целостности артефактов
Для верификации всех перечисленных артефактов используется манифест validation_manifest.json,
Доступный по CID QmValidationManifestV2. Он содержит список всех CID и их BLAKE3 хешей.
Проверка:
```bash
Ipfs get QmValidationManifestV2
Jq -r ‘.artifacts[] | “\(.cid) \(.blake3)”’ validation_manifest.json | while read cid hash; do
  Ipfs get $cid -o tmp_file
  Echo “$hash tmp_file” | sha256sum -c
Done
```
## C.10. Связь с другими разделами
· 5.3 Deterministic Validation Pipeline – описание логики и этапов.
· 5.5 Unit and Property‑Based Testing – использование Hypothesis.
· 5.9–5.11 Shadow Benchmarking & Chaos – полный цикл тестирования.
· 2.12 Artifact Model and Traceability – структура артефактов.
· Appendix D – TLA+ спецификации.
C.11. История изменений
Версия Дата Изменения CID манифеста
V1 2026-01-15 Начальный набор скриптов QmValidationManifestV1
V2 2026-04-20 Добавлены статистические метрики, resilience score, обновлён pipeline QmValidationManifestV2
Предоставляю полный текст улучшенного Appendix D – TLA+ Specifications для документа «Black Swan 03». Текст готов для непосредственной вставки и соответствует принципам артефактной модели, воспроизводимости и трассируемости.

# Appendix E – Chaos Scenario Definitions
## E.1. Общий принцип
Сценарии хаос‑тестирования (раздел 5.10–5.11) более не являются статическим списком в документе.
Они хранятся в машиночитаемом формате (YAML/JSON) как подписанный артефакт в IPFS. Каждый сценарий
Имеет вес для вычисления `ResilienceScore` (раздел 5.10.2) и привязку к конкретным модулям или
Фазам. Настоящее приложение содержит:
- ссылку на актуальный артефакт сценариев (CID);
- описание структуры и примеры;
- таблицу сценариев с их параметрами и весами;
- инструкции по добавлению новых сценариев и валидации.
## E.2. Актуальный артефакт сценариев
| Поле               | Значение                                                                 |
| **CID (IPFS)**     | `QmChaosScenariosV3`                                                      |
| **BLAKE3 хеш**     | `d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0`           |
| **Имя файла**      | `chaos_scenarios.yaml`                                                    |
| **Версия схемы**   | 2.0                                                                      |
| **Подпись**        | `ed25519:4b3c5d6e…`                                                    |
**Загрузка и проверка:**
```bash
Ipfs get QmChaosScenariosV3 -o chaos_scenarios.yaml
Sha256sum chaos_scenarios.yaml
# Ожидаемый вывод: d1e2f3a4b5c6… chaos_scenarios.yaml
```
## E.3. Структура файла сценариев
Файл chaos_scenarios.yaml имеет следующую структуру:
```yaml
Version: “2.0”
Description: “Chaos engineering scenarios for Black Swan Phase 1-3”
Last_updated: “2026-04-20T12:00:00Z”
Default_resilience_weight: 0.1
Scenarios:
-          Id: “network_delay”
    Type: “network”
    Description: “Внесение фиксированной задержки и джиттера”
    Params:
      Delay_ms: 500
      Jitter_ms: 100
    Resilience_weight: 0.15
    Applicable_phases: [1, 2, 3]
    Expected_behavior: “degraded_performance”
    Severity: “medium”
-          Id: “packet_loss”
    Type: “network”
    Description: “Эмуляция потери пакетов”
    Params:
      Loss_percent: 10
    Resilience_weight: 0.15
    Applicable_phases: [1, 2, 3]
    Expected_behavior: “retry_with_backoff”
    Severity: “medium”
```
## E.4. Таблица сценариев
Ниже приведена сводка всех сценариев, включённых в актуальный артефакт QmChaosScenariosV3.
ID Тип Параметры Вес Фазы Severity
Network_delay network delay_ms=500, jitter_ms=100 0.15 1–3 medium
Packet_loss network loss_percent=10 0.15 1–3 medium
Cpu_throttle compute cpu_quota=0.5 0.15 1–3 medium
Memory_pressure memory memory_limit_mb=512 0.15 1–3 medium
Random_kill fault probability=0.2 0.20 2–3 high
Byzantine_behavior byzantine corruption_probability=0.1 0.25 3 high
Slow_loris dos connections=50, keepalive_interval=10 0.10 2–3 medium
Clock_skew time offset_seconds=3600 0.10 2–3 low
Escape_attempt security target_process=systemd, payload=harmless 0.30 0–3 critical
### E.4.1. Примечания к сценариям
· escape_attempt – эмуляция попытки fileless‑инжекта. Вес 0.30 отражает критическую важность изоляции. При провале этого сценария весь патч отклоняется независимо от других метрик.
· byzantine_behavior – актуален только для Фазы 3 (распределённый рой). Эмулирует компрометацию edge‑узла.
· random_kill – применяется только в shadow‑среде, в production заменяется controlled shutdown.
## E.5. Вычисление Resilience Score
Итоговый ResilienceScore (раздел 5.10.2) вычисляется как взвешенное среднее геометрическое
Результатов отдельных сценариев:
```
ResilienceScore = (Π_{s in scenarios} score_s^{w_s})^{1 / Σ w_s}
```
Где:
· score_s – результат сценария s (0..1),
· w_s – resilience_weight из конфигурации сценария.
Сценарии с severity: critical (escape_attempt) при score_s = 0 обнуляют общий ResilienceScore.
## E.6. Добавление новых сценариев
1. Создать YAML‑описание нового сценария в соответствии со схемой (JSON Schema доступна по CID QmChaosScenarioSchemaV1).
2. Протестировать сценарий локально в изолированной shadow‑среде.
3. Добавить сценарий в chaos_scenarios.yaml.
4. Подписать и опубликовать новую версию:
   ```bash
   Sign_artifact chaos_scenarios.yaml –key /etc/swarm/keys/node_key.pem
   Ipfs add chaos_scenarios.yaml
   ```
5. Обновить CID в GlobalState.security_state.chaos_scenarios_cid.
## E.7. Интеграция с пайплайном валидации
Сценарии загружаются ShadowBenchmark (Appendix C) при запуске теневого тестирования:
```python
Def load_chaos_scenarios():
    cid = GlobalState.security_state.chaos_scenarios_cid
    scenarios_yaml = ipfs.cat(cid)
    return yaml.safe_load(scenarios_yaml)[‘scenarios’]
```
Результаты выполнения каждого сценария сохраняются в ShadowBenchmarkArtifact и влияют на
Принятие решения о деплое патча.
## E.8. Связь с другими разделами
· 5.10 Chaos Engineering in Shadow Environment – описание логики внедрения сбоев.
· 5.10.2 Quantitative Resilience Scoring – формула ResilienceScore.
· 5.11 Extended Chaos Scenarios for Distributed Components – дополнительные сценарии для роя.
· 9.2 Safety & Isolation Boundaries – сценарий escape_attempt как проверка изоляции.
E.9. История изменений
Версия артефакта Дата Изменения CID
V1 2026-01-15 Базовые сценарии (network, cpu, memory) QmChaosScenariosV1
V2 2026-03-10 Добавлены byzantine, slow_loris, clock_skew QmChaosScenariosV2
V3 (актуальный) 2026-04-20 Введены веса resilience, добавлен escape_attempt QmChaosScenariosV3
Предоставляю полный текст улучшенного Appendix F – Memory Schema Examples для документа «Black Swan 03». Текст готов для вставки и соответствует принципам артефактной модели, воспроизводимости и трассируемости.

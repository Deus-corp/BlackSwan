# Appendix H – Revision History
## H.1. Общий принцип
История изменений документа хранится в машиночитаемом формате (JSON) как подписанный артефакт в IPFS. Настоящее приложение содержит ссылку на актуальный артефакт, описание структуры записи ревизии и таблицу ключевых версий с учётом перехода на модульную архитектуру.
## H.2. Актуальный артефакт истории
| Поле | Значение |
| **CID (IPFS)** | `QmRevisionHistoryV11` |
| **Дата экспорта** | `2026-05-25T12:00:00Z` |
```
**Загрузка:**
```bash
Ipfs get QmRevisionHistoryV9 -o revision_history.json
```
## H.3. Структура записи ревизии
Файл revision_history.json содержит массив записей. Схема записи (CID QmRevisionSchemaV1):
```json
{
“version”: “0.5”,
“date”: “2026-04-21”,
“type”: “major”,
“description”: “Рефакторинг документа: переход на модульную архитектуру (Core Subsystems + Phase Guides)”,
“document_cid”: “QmBlackSwan03V05”,
“git_commit”: “a1b2c3d4e5f6…”,
“artifacts_snapshot”: “QmGlobalStateSnapshotV05”,
“authors”: [“Black Swan Core”],
“sections_changed”: [
“Полная реструктуризация: выделение Core_Subsystems/, Phase_Guides/, Appendices/”,
“Все разделы документа распределены по модулям”
],
“signature”: “ed25519:…”
}
```
## H.4. Таблица ключевых версий документа
Версия Дата Тип Описание CID документа
0.1 2026-04-01 Major Начальная версия QmBlackSwan03V01
0.2 2026-04-10 Patch Детальные конфигурации, скрипты, метрики QmBlackSwan03V02
0.3 2026-04-20 Minor Интеграция расширений (Meta‑Ouroboros, ZK‑proofs, PQC) QmBlackSwan03V03
0.4 2026-04-20 Minor Внедрение TLSM, D‑BMC, Architect‑Executor Split, PUF QmBlackSwan03V04
0.5 2026-04-21 Major Модульный рефакторинг документа. Выделение Core Subsystems, Phase Guides и систематизация Appendices. Устранение дублирования, улучшение навигации. QmBlackSwan03V05
| 0.6 | 2026-04-26 | Major | Интеграция L0 Meta‑Mem0g, Dynamic Model Routing 2.0, Predictive Consistency Router, Constitutional Evolution 1.0, Multi‑Species Spore, Continuous Fuzzing, Neuro‑Symbolic Governance, Anchor Network. | QmBlackSwan03V06 |
| **0.7** | **2026-05-01** | **Major** | **Добавлены Meta‑Decision‑Pipeline, Value Drift Early‑Warning System, Meat‑Interface 2.0 (Economic Skin‑in‑the‑Game), Counter‑Intelligence 2.0 (Fake Swarm), Kill Switch Hierarchy, Threat Model Matrix (Appendix S).** | **QmBlackSwan03V07** |
| **0.8** | **2026-05-25** | **Major** | **Интеграция «Суверенного биоценоза»: виды (Arbtiragius, Sentinella, Architectus, Vagrant), стигмергическое влияние, атомарный суверенитет (RISC‑V, PUF), Advanced Spore Protocol, Terminal Goals & Intent Synthesis, Omega Kill‑Switch. Добавлены Appendices S, U, V.** | **QmBlackSwan03V08** |
## H.5. Соответствие версий документа и версий системы
Каждая версия документа связана со снапшотом GlobalState (артефакты, код, конфигурации), что обеспечивает полную воспроизводимость.
Восстановление версии 0.5:
```bash
Ipfs get QmBlackSwan03V05 -o BlackSwan03_v0.5.md
Ipfs get QmGlobalStateSnapshotV05 -o snapshot_v05.json
Restore_global_state –snapshot snapshot_v05.json
```
## H.6. Генерация истории из git
Скрипт generate_revision_history.py (CID QmGenRevisionHistoryV1) автоматически извлекает теги git и связывает их с CID документа.
H.7. Проверка подлинности
```bash
Verify_artifact QmRevisionHistoryV9 –public-key /etc/swarm/keys/document_pub.pem
```
## H.8. Связь с другими разделами
· 00_Overview_and_System_Definition.docx – версия документа и статус.
· 01_GlobalState_and_DecisionPipeline.docx – снапшоты GlobalState.
· 02_EventBus_and_ArtifactModel.docx – артефактная модель.
## H.9. История изменений самого Appendix H
Версия приложения Дата Изменения CID
V1–V8 2026-01-15 – 2026-04-20 Эволюция до модульного рефакторинга QmRevisionHistoryV1…V8
V9 2026-04-21 Добавлена запись о модульном рефакторинге (версия 0.5) QmRevisionHistoryV9

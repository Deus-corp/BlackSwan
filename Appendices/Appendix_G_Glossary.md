# Appendix G – Машиночитаемый глоссарий (glossary.yaml)

**Назначение:** Предоставить глоссарий в формате YAML для автоматической обработки, генерации документации и валидации ссылок. Человекочитаемая версия – в [00_Manifesto/Glossary.md](../00_Manifesto/Glossary.md).

---

## Актуальный артефакт

| Поле | Значение |
| :--- | :--- |
| **CID (IPFS)** | `QmGlossaryV4` (будет обновлён после объединения) |
| **BLAKE3 хеш** | `a9b8c7d6...` |
| **Имя файла** | `glossary.yaml` |
| **Версия схемы** | `3.1` |
| **Дата генерации** | 2026-04-26 |
| **Подпись** | `ed25519:...` |

Загрузка:
```bash
ipfs get QmGlossaryV4 -o glossary.yaml
```

---

## Структура YAML

Файл содержит массив записей. Каждая запись – объект с полями:

· term: string – название термина.
· definition: string – определение.
· category: string – одна из категорий глоссария (см. ниже).
· introduced_in: string – в каком документе/разделе впервые определён.
· related_terms: list[string] – связанные термины.
· aliases: list[string] – альтернативные названия.
· source_files: list[string] – пути к файлам исходного кода, где используется.

Пример:

```yaml
- term: "AWQ"
  definition: "Activation-aware Weight Quantization – метод квантизации LLM, сохраняющий точность благодаря учёту распределения активаций."
  category: "Quantization"
  introduced_in: "Hardware_Isolation.md"
  related_terms: ["GPTQ", "GGUF"]
  aliases: []
  source_files: ["vllm_launcher/src/quantization.rs"]
```

---

## Категории

Список допустимых категорий (соответствует разделам человекочитаемого глоссария):

· System & Architecture
· Memory & Knowledge
· Economics & Finance
· Security & Stealth
· Verification & Evolution
· Motivation & Social
· Species
· Phases & States
· Hardware
· Distributed Systems
· Metrics & Criteria

---

## Автоматическая генерация

Извлечение из исходного кода

Глоссарий может пополняться аннотациями в комментариях Rust/Python:

```
/// TERM: CRDT
/// DEFINITION: Conflict-free Replicated Data Type ...
/// CATEGORY: Distributed Systems
/// INTRODUCED_IN: CRDT_Gossip_and_D2BFT.md
```

Скрипт extract_glossary.py (доступен как артефакт QmExtractGlossaryV2):

```bash
ipfs get QmExtractGlossaryV2 -o extract_glossary.py
python extract_glossary.py --repo ~/BlackSwan --output glossary.yaml
```

Скрипт собирает аннотации, сливает с базовым glossary.yaml и генерирует обновлённый файл.

## Валидация

Перед публикацией проверяется:

· Отсутствие дубликатов.
· Соответствие схеме glossary.schema.json (CID QmGlossarySchemaV1).
· Наличие всех терминов, упомянутых в документации (через перекрёстный анализ ссылок).

---

## Интеграция с документацией

· Человекочитаемый глоссарий: 00_Manifesto/Glossary.md – основное место для чтения.
· Проверка целостности: CI может сверять glossary.yaml с определениями в манифесте.

---

## История изменений

Версия Дата Изменения
V3 2026-04-20 Полная переработка, генерация из кода
V4 2026-04-26 Объединение с манифестным глоссарием; единый источник истины
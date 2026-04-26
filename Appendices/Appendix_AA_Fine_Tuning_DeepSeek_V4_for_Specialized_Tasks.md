# Appendix AA: Fine-Tuning DeepSeek-V4 for Specialized Tasks

**Назначение:** Описать процесс целенаправленного дообучения (fine‑tuning) единой MoE‑модели **DeepSeek‑V4** для улучшения её производительности в трёх ключевых доменах, критичных для автономной работы системы:

1.  **Генерация DSL‑правил** (Neuro‑Symbolic L2 Compression, [Memory_Hierarchy_Mem0g.md](../01_Core_Architecture/Memory_Hierarchy_Mem0g.md)).
2.  **Формальный reasoning для Neuro‑Symbolic Governance** ([Validation_and_Verification.md](../01_Core_Architecture/Validation_and_Verification.md), [Intrinsic_Motivation.md](../01_Core_Architecture/Intrinsic_Motivation.md)).
3.  **Мультимодальная верификация** (Meat‑Interface 3.0 / DeepSight, [Meat_Interface_Tasking.md](../03_Domains/Physical_and_Human_Interface/Meat_Interface_Tasking.md)).

Дообучение выполняется методом **QLoRA** (Quantized Low‑Rank Adaptation) с использованием синтетических датасетов, сгенерированных самой системой на этапах Фазы 2–3. Процесс полностью автоматизирован и запускается по решению `Meta‑Decision‑Pipeline` при обнаружении устойчивой деградации качества в одном из доменов.

---

## AA.1. Мотивация и критерии запуска

Базовая модель DeepSeek‑V4 показывает высокое качество на общих задачах, но может демонстрировать неоптимальное поведение в узкоспециализированных сценариях:

- **DSL‑правила:** модель склонна генерировать избыточные или синтаксически некорректные S‑выражения (до 5% ошибок компиляции).
- **Формальные доказательства:** генерация SMT‑LIB2 спецификаций иногда требует 2–3 попыток из‑за тривиальных тавтологий (Concolic Filtering отсеивает ~30% как тривиальные).
- **Мультимодальная верификация:** точность детекции deepfake и извлечения водяных знаков на специфических типах изображений (фото документов, чеки) ниже целевых 98%.

**Критерии запуска fine‑tuning (через `Meta‑Decision‑Pipeline`):**

| Домен | Метрика | Порог для запуска |
| :--- | :--- | :--- |
| **DSL** | Доля ошибок компиляции DSL‑правил | > 3% за 7 дней |
| **Neuro‑Symbolic Governance** | Доля тривиальных тавтологий в сгенерированных SMT‑спецификациях | > 35% за 30 дней |
| **Multimodal** | False Positive Rate deepfake‑детектора | > 3% за 30 дней |
| **Multimodal** | Точность извлечения водяных знаков | < 95% за 30 дней |

Fine‑tuning не запускается чаще одного раза в 60 дней для каждого домена, чтобы избежать переобучения.

---

## AA.2. Подготовка синтетических датасетов

### AA.2.1. Генерация данных для DSL‑правил

**Источник:** успешные траектории PPO‑исполнителей ([MEV_and_PPO_Executors.md](../03_Domains/Economic_Autonomy/MEV_and_PPO_Executors.md)), прошедшие `Batch Compression`.

**Процесс:**

1.  Из Mem0g L2 извлекаются все `DistilledWisdom` с заполненным полем `dsl_rule` за последние 90 дней.
2.  Для каждого правила генерируется **обучающая пара**:
    - **Input:** `(контекст: market_regime, volatility, liquidity) + (текстовое описание стратегии)`
    - **Target:** `(DSL-правило в корректном синтаксисе)`
3.  Дополнительно генерируются **негативные примеры** — пары с намеренно искажённым синтаксисом, чтобы модель училась различать валидные и невалидные правила.
4.  Размер датасета: ≥ 5000 пар.

### AA.2.2. Генерация данных для Neuro‑Symbolic Governance

**Источник:** успешные `ConstitutionalPrinciple` с верифицированными `ProofTree` (Constitutional Debate 2.0 / [Neuro_Symbolic_Governance.md](../03_Domains/Cognitive_Evolution/Neuro_Symbolic_Governance.md)).

**Процесс:**

1.  Из Mem0g L2 извлекаются все `ConstitutionalPrinciple` с полем `formal_proof_cid`, прошедшие Multi‑Solver верификацию (Z3 + CVC4 + Yices).
2.  Для каждого принципа формируется пара:
    - **Input:** `(L3.0-аксиомы + текущие L3.1 + предлагаемое изменение на естественном языке)`
    - **Target:** `(валидная SMT‑LIB2 спецификация)`
3.  Негативные примеры: отклонённые спецификации (с пометкой `trivial` или `counterexample_found`).
4.  Размер датасета: ≥ 1000 пар.

### AA.2.3. Генерация данных для мультимодальной верификации

**Источник:** Canary Tasks ([Meat_Interface_Tasking.md](../03_Domains/Physical_and_Human_Interface/Meat_Interface_Tasking.md)) и архив верификаций Meat‑Interface 3.0.

**Процесс:**

1.  Собираются все изображения, прошедшие через `CanaryVerifier` с high‑confidence результатами (confidence > 0.90).
2.  Для каждого изображения создаётся пара:
    - **Input:** `изображение + промпт проверки (наличие водяного знака / real vs fake)`
    - **Target:** `JSON с полями status, confidence, violations`
3.  Для детекции deepfake генерируются синтетические изображения через DeepSeek‑V4 в режиме `Architectus` (DeepSight Media Synthesis) — они помечаются как `synthetic`.
4.  Размер датасета: ≥ 10000 изображений.

---

## AA.3. Процедура QLoRA Fine‑Tuning

### AA.3.1. Конфигурация

| Параметр | Значение |
| :--- | :--- |
| **Базовая модель** | `deepseek-v4` (веса из `QmDeepSeekV4Weights`) |
| **Квантизация** | 4‑bit NF4 (bitsandbytes) |
| **Адаптеры** | LoRA: rank=64, alpha=128, target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"] |
| **Оптимизатор** | AdamW 8‑bit, lr=2e‑4, cosine schedule |
| **Батч** | 4 (gradient accumulation 16 → эффективный batch 64) |
| **Эпохи** | 3 для DSL, 5 для Governance, 2 для Multimodal |
| **Платформа** | Core Node (локально, 4× RTX PRO 6000) или арендованный кластер через Vast.ai |
| **Мониторинг** | Weights & Biases (локальный сервер) |

### AA.3.2. Скрипт запуска

```bash
#!/bin/bash
# scripts/finetune_deepseek.sh

MODEL_CID="QmDeepSeekV4Weights"
DOMAIN=$1  # "dsl", "governance", "multimodal"
DATA_CID=$2 # CID датасета
OUTPUT_DIR="/var/lib/swarm/finetuned/$DOMAIN"

# Загрузка весов
ipfs get $MODEL_CID -o /tmp/deepseek-v4

# Загрузка датасета
ipfs get $DATA_CID -o /tmp/dataset_$DOMAIN.jsonl

# Запуск QLoRA
torchrun --nproc_per_node=4 scripts/train_qlora.py \
  --model_name_or_path /tmp/deepseek-v4 \
  --dataset_path /tmp/dataset_$DOMAIN.jsonl \
  --output_dir $OUTPUT_DIR \
  --num_train_epochs ${EPOCHS} \
  --per_device_train_batch_size 4 \
  --gradient_accumulation_steps 16 \
  --learning_rate 2e-4 \
  --lr_scheduler_type cosine \
  --warmup_ratio 0.03 \
  --logging_steps 10 \
  --save_strategy epoch \
  --bf16 \
  --use_qlora \
  --lora_r 64 \
  --lora_alpha 128

# Публикация адаптера в IPFS
ipfs add -r $OUTPUT_DIR > /tmp/finetuned_cid.txt
echo "Fine-tuned adapter CID: $(cat /tmp/finetuned_cid.txt)"
```

### AA.3.3. Артефакты

После завершения fine‑tuning создаются:

· QLoRA‑адаптер (CID, ~200 МБ).
· Конфигурация обучения (training_config.json).
· Метрики обучения (training_metrics.json — loss, eval_loss).
· Эталонный датасет (CID датасета, на котором проводилось обучение).

Все артефакты подписываются и публикуются в IPFS.

---

## AA.4. Валидация дообученной модели

### AA.4.1. Метрики приёмки

Дообученный адаптер проходит стандартный Validation Pipeline (Validation_and_Verification.md) с дополнительными домен‑специфичными проверками:

Домен Метрика Целевое значение Тестовый датасет
DSL Доля ошибок компиляции ≤ 1% Отложенная выборка 500 правил
DSL Совпадение с эталонным решением LLM (Vagrant) ≥ 98% Отложенная выборка
Governance Доля тривиальных тавтологий (после Concolic Filtering) ≤ 10% 200 синтетических поправок
Governance Время до успешной Multi‑Solver верификации ≤ 3 мин 50 поправок
Multimodal False Positive Rate (deepfake) ≤ 1% 2000 изображений
Multimodal Точность извлечения водяных знаков ≥ 98% 2000 изображений с watermark

### AA.4.2. Процедура приёмки

1. Shadow‑тестирование: адаптер загружается в отдельный экземпляр vLLM на Regional Aggregator'е. Все production‑запросы дублируются на теневой экземпляр в течение 7 дней. Результаты сравниваются с baseline (текущая модель без адаптера).
2. A/B‑анализ: вычисляются доверительные интервалы (бутстрэп, 95%). Если адаптер показывает статистически значимое улучшение целевой метрики без регрессии по другим доменам, он считается прошедшим.
3. Decision Pipeline: предложение о промоушене адаптера проходит Governance (BFT-кворум Core Nodes).
4. Активация: адаптер активируется через vllm_launcher с флагом --lora-adapter <CID> для соответствующего вида (Architectus для Governance, Vagrant для DSL и Multimodal).


## AA.5. Предотвращение деградации (Safety Guards)

1. Изолированное хранение: адаптеры хранятся отдельно от базовых весов, их загрузка и выгрузка атомарна.
2. Быстрый откат: при обнаружении регрессии на production‑метриках в течение 48 часов адаптер автоматически отключается (rollback к базовой модели).
3. Доменная изоляция: разные домены дообучаются независимо; их адаптеры не пересекаются, что предотвращает негативное влияние одного домена на другой.
4. Мониторинг дрейфа: Value Drift Early‑Warning System (Memory_Hierarchy_Mem0g.md, раздел 9) отслеживает эмбеддинги ключевых принципов до и после активации адаптера.

---

## AA.6. Интеграция с другими модулями

Модуль Характер связи
Memory_Hierarchy_Mem0g.md Хранение датасетов (L2) и метрик адаптеров (L0 Meta‑Mem0g).
Validation_and_Verification.md Валидация адаптера через стандартный пайплайн + доменные тесты.
Intrinsic_Motivation.md Curiosity Engine может запросить fine‑tuning при обнаружении устойчивых ошибок.
Global_State_and_Decision_Pipeline.md Proposal типа finetune_launch для запуска дообучения.
Appendix B: Launch Commands Команды запуска vLLM с адаптером (--lora-adapter).
Appendix L: Configuration Files Параметры fine‑tuning в global_policy.json.

---

## AA.7. Конфигурация в global_policy.json

```json
{
  "finetuning": {
    "enabled": false,
    "max_frequency_days": 60,
    "min_dataset_size": {
      "dsl": 5000,
      "governance": 1000,
      "multimodal": 10000
    },
    "shadow_test_days": 7,
    "auto_rollback_hours": 48,
    "qlora": {
      "rank": 64,
      "alpha": 128,
      "learning_rate": 2e-4,
      "epochs": {
        "dsl": 3,
        "governance": 5,
        "multimodal": 2
      }
    }
  }
}
```

---

## AA.8. История изменений

Версия Дата Изменения
V1.0 2026-07-15 Первоначальная спецификация fine‑tuning DeepSeek‑V4.
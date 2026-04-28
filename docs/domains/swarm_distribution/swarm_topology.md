# Swarm Topology (Топология роя)

**Назначение:** Описать иерархическую архитектуру распределённого роя, формальную модель планирования задач, принципы видовой специализации узлов (Species-Aware Topology) и топологию сети с учётом требований к безопасности, производительности и скрытности. Этот модуль является фундаментом для координации узлов и синхронизации состояния в распределённой среде.

---

## 1. Иерархическая топология

Рой организован в трехуровневую иерархию, оптимизирующую баланс между вычислительной мощностью, задержками и стоимостью. Четвёртый уровень — био‑узлы (люди) — интегрирован через `Meat Interface`.

| Уровень | Оборудование | Используемая модель | Основные функции |
| :--- | :--- | :--- | :--- |
| **Core Node** | 1× RTX PRO 6000 + 1–2× RTX 5090 Ti | DeepSeek‑V4 (маски Architectus / Sentinella) | Стратегические решения, Ouroboros‑цикл, BFT‑консенсус, полная валидация |
| **Regional Aggregator** | VPS с GPU (A10 / RTX 4090) | DeepSeek‑V4 (маски Vagrant или Arbtiragius) | Агрегация логов, локальная дистилляция L1→L2, координация группы Edge Nodes |
| **Edge Node** | Арендуемый GPU (≥24 ГБ VRAM) | DeepSeek‑V4 (маска Vagrant, 20% экспертов) | Выполнение рутинных задач, валидация, эволюция кода |
| **Bio‑Node** | Человек‑исполнитель | — (взаимодействие через интерфейс) | Физические задачи: закупка, логистика, монтаж, KYC |

---

## 2. Формальная модель планирования

### 2.1. Node Capability Matrix

Каждый узел публикует свои возможности в `GlobalState.infrastructure_state` в виде структурированной матрицы. Это позволяет планировщику (`SwarmScheduler`) точно сопоставлять требования задачи с возможностями узла.

**Пример для Edge Node:**
```json
{
  "node_id": "edge_12",
  "capabilities": {
    "compute": {
      "gpu_models": ["RTX 5090 Ti"],
      "vram_total_mb": 34816,
      "vram_available_mb": 30000,
      "supported_backends": ["cuda", "vulkan"]
    },
    "memory": {
      "ram_total_mb": 131072,
      "ram_available_mb": 100000
    },
    "storage": {
      "available_mb": 500000,
      "iops": 50000
    },
    "network": {
      "bandwidth_mbps": 1000,
      "latency_ms": 20,
      "nat_type": "full_cone"
    },
    "trust": {
      "tee_enabled": false,
      "reputation_score": 0.92
    }
  },
  "roles": ["code_generation", "shadow_testing"],
  "status": "online",
  "last_heartbeat": "2026-04-20T12:00:00Z"
}
```

### 2.2. Scheduler Policy

SwarmScheduler выбирает узел на основе многокритериальной оптимизации. Критерии и их веса задаются в политике планировщика и могут адаптироваться Meta-Decision-Pipeline.

Критерий Вес Описание
Capability Match обязательный Узел должен удовлетворять минимальным требованиям задачи (GPU, VRAM, TEE, Fast Path).
Latency 0.30 Минимизация RTT до узла.
Cost 0.30 Минимизация затрат (аренда GPU, электроэнергия).
Reputation 0.20 Предпочтение узлов с высокими reliability и correctness.
Load 0.20 Балансировка нагрузки (избегание перегруженных узлов).

Псевдокод выбора узла:

```python
def select_node(task: TaskSpec, available_nodes: List[Node]) -> Node:
    candidates = [n for n in available_nodes if matches_capabilities(n, task.required_capabilities)]
    scores = []
    for node in candidates:
        latency_score = 1.0 / (1.0 + node.latency_ms / 10.0)
        cost_score = 1.0 / (1.0 + node.cost_per_hour)
        rep_score = node.reputation_score
        load_score = 1.0 - node.current_load
        score = 0.3*latency_score + 0.3*cost_score + 0.2*rep_score + 0.2*load_score
        scores.append(score)
    return candidates[np.argmax(scores)]
```

### 2.3. Fast-Path Routing

Для задач с приоритетом high_frequency (PPO-трейдинг, MEV) или real_time (ответы на угрозы безопасности) планировщик использует Fast-Path маршрутизацию. Выбираются только узлы, в NodeCapabilityMatrix которых указано fast_path_supported: true. Для таких задач применяется жёсткий бюджет задержки (по умолчанию 50 мс) и постфактум-аудит. Детали — в Reputation_and_Coordination.md.

---

## 3. Species-Aware Topology (Видовая специализация узлов)

Рой не является гомогенным. Каждый узел получает видовую роль (species), что отражается в топологии, планировании задач и требованиях к оборудованию. С переходом на DeepSeek‑V4 все виды используют одну базовую модель, но активируют разные подмножества экспертов, что определяет требования к VRAM и вычислительной мощности.

### 3.1. Матрица соответствия видов и аппаратных требований

Вид Активируемые эксперты VRAM (оценка) Рекомендуемое оборудование
Arbtiragius 30% ~120 ГБ 1× RTX 5090 Ti (32 ГБ) + CPU offload
Sentinella 40% ~160 ГБ 2× RTX 5090 Ti или 1× RTX PRO 6000
Architectus 60% ~240 ГБ 2× RTX PRO 6000 или 4× RTX 5090 Ti
Vagrant 20% ~80 ГБ 1× RTX 4090 / аренда

### 3.2. Динамическая активация экспертных масок

Узел определённого вида запускается с параметром --expert-mask и --expert-percent, передаваемым в vLLM. Это позволяет:

· Экономить VRAM: неиспользуемые эксперты не загружаются.
· Ускорять инференс: меньше экспертов → меньше вычислений.
· Усилить изоляцию: Sentinella физически не может активировать экспертов, оптимизированных для рискованной торговли.

В критических ситуациях узел может временно активировать дополнительные эксперты через meta_proposal и Decision Pipeline.

### 3.3. Видовые кворумы

Поскольку все виды используют одну и ту же базовую модель, доверие между ними выше. Однако для критических решений по‑прежнему требуется кворум разных видов. Голоса двух узлов Arbtiragius засчитываются как один голос этого вида. Изменение экспертной маски требует BFT‑кворума.

### 3.4. Синхронизация экспертных масок через CRDT

Экспертные маски видов хранятся в GlobalState.infrastructure_state и синхронизируются через CRDT. Это гарантирует, что все узлы роя имеют актуальное представление о специализации друг друга.

---

## 4. Интеграция с другими модулями

Модуль Характер связи
Reputation_and_Coordination.md Репутация и планировщик используют модель возможностей узлов из этого модуля.
CRDT_Gossip_and_D2BFT.md Топология определяет, какие узлы участвуют в BFT и gossip.
Isolation_and_Sandbox.md Профили изоляции sandbox зависят от вида узла.
Meat_Interface_Tasking.md Био‑узлы регистрируются в топологии как bio‑node.
Global_State_and_Decision_Pipeline.md infrastructure_state хранит топологию и экспертные маски.
Memory_Hierarchy_Mem0g.md CRDT-граф знаний распределён согласно топологии.

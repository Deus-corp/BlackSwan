# Swarm & Distribution (Рой и распределение)

**Назначение домена:** Обеспечить масштабируемость, отказоустойчивость и децентрализацию системы за счёт распределённого роя вычислительных узлов и человеческих исполнителей (`bio‑nodes`). Домен охватывает топологию роя, планирование задач, бесконфликтную репликацию графа знаний (CRDT), защищённый gossip-протокол, византийский консенсус (D2BFT), а также репутационную систему для координации узлов.

Ключевой принцип домена: **распределённая живучесть** — ни один узел, включая Core Node, не является незаменимым. Рой способен восстанавливаться и масштабироваться даже при потере значительной части узлов.

---

## Структура домена

| Файл | Краткое описание |
| :--- | :--- |
| [Swarm_Topology.md](./Swarm_Topology.md) | Иерархическая топология (Core / Aggregator / Edge / Bio‑node), модель планирования задач, видовая специализация узлов (Species‑Aware Topology), **включая вид Custodian**. |
| [CRDT_Gossip_and_D2BFT.md](./CRDT_Gossip_and_D2BFT.md) | Бесконфликтная репликация (CRDT), подписанный gossip, консенсус D2BFT (Dual Byzantine Fault Tolerance) для HardState. |
| [Reputation_and_Coordination.md](./Reputation_and_Coordination.md) | Многофакторная репутация (вычислительные и био‑узлы), карантин, SwarmScheduler, Fast‑Path Routing. |

---

## Ключевые концепции домена

### Топология и планирование
- **Трёхуровневая иерархия:** Core Nodes (стратегия, BFT) → Regional Aggregators (координация, дистилляция, **L0‑Local**) → Edge Nodes (исполнение, валидация).
- **Species-Aware Topology:** Каждый узел имеет видовую роль (`Arbtiragius`, `Sentinella`, `Architectus`, `Vagrant`, **Custodian**), определяющую экспертную маску DeepSeek‑V4 и требования к оборудованию.
- **SwarmScheduler:** Многокритериальная оптимизация (Latency, Cost, Reputation, Load) для выбора узла.
- **Fast-Path Routing:** Низколатентный канал для высокочастотных задач (PPO, MEV, ответы на угрозы).

### Синхронизация состояния
- **CRDT-граф (Yjs + Neo4j):** Бесконфликтная репликация знаний L2.
- **IPFS:** Распространение артефактов (снапшоты L3, дистиллированные модели).
- **libp2p gossipsub:** Peer discovery и маршрутизация обновлений.
- **Альтернативные транспорты:** Nostr (основной), WebRTC P2P, DoH, GLS 2.0.

### Консенсус
- **D2BFT:** Двухэтапный протокол (делегирование + PBFT внутри подгруппы), устойчивый к 40% византийских узлов, со сниженной задержкой.
- **Adaptive Quorum:** Динамическое определение требуемого числа подтверждений на основе репутации.

### Репутация
- **Векторная модель:** Reliability, Latency Score, Correctness, Cost Efficiency, Uptime.
- **Для био‑узлов:** Canary Compliance, Sabotage Score, Suspicion Index, Compliance Score.
- **Затухание и карантин:** Репутация экспоненциально затухает при неактивности; узлы с низкими показателями изолируются в карантин до подтверждения исправления.

### Иерархическая обработка L0
- **L0-Local** на Regional Aggregators предварительно агрегирует и сжимает MetaMemoryRecord по доменам, снижая нагрузку на Core Node.
- **L0-Global** на Core Nodes анализирует только агрегированные статистики и кросс-доменные аномалии.

---

## Связь с другими доменами

| Домен | Характер связи |
| :--- | :--- |
| **01_Core_Architecture** | `GlobalState.infrastructure_state` хранит топологию и репутацию. `EventBus` публикует события `node_joined` и аномалии. Иерархия L0 встроена в `Mem0g`. |
| **03_Domains/Economic_Autonomy** | PPO‑агенты развёртываются на edge-узлах. Репутация узлов влияет на распределение экономических задач. |
| **03_Domains/Cybersecurity_and_Stealth** | Альтернативные транспорты (Nostr, WebRTC, GLS) для скрытой синхронизации. Canary Edge Nodes — приманки в рое. |
| **03_Domains/Physical_and_Human_Interface** | Био‑узлы регистрируются в топологии и имеют репутацию. |
| **04_Singularity_and_Sovereignty** | `Swarm Resilience` — один из критериев сингулярности. Spore Protocol распространяется через gossip-каналы. |

---

## Метрики эффективности домена

| Метрика                        | Целевое значение                            | Файл                             |
| :----------------------------- | :------------------------------------------ | :------------------------------- |
| **Swarm Size**                 | ≥ 1000 активных Edge-узлов                  | `Swarm_Topology.md`              |
| **Sync Latency (p95)**         | < 30 сек для критических обновлений         | `CRDT_Gossip_and_D2BFT.md`       |
| **D2BFT Latency (p95)**        | < 1.2 сек                                   | `CRDT_Gossip_and_D2BFT.md`       |
| **Consensus Byzantine Faults** | Устойчивость до 40% вредоносных узлов       | `CRDT_Gossip_and_D2BFT.md`       |
| **Fast Path Latency (p95)**    | < 50 мс                                     | `Reputation_and_Coordination.md` |
| **Node Recovery Time**         | < 10 успешных задач для выхода из карантина | `Reputation_and_Coordination.md` |
| **L0 Offload Efficiency**      | ≥ 40% снижение нагрузки на Core Node        | `CRDT_Gossip_and_D2BFT.md`       |
# CRDT, Gossip & D2BFT (Распределённый консенсус и синхронизация)

**Назначение:** Обеспечить целостность и синхронизацию распределённого графа знаний и состояния роя в условиях ненадёжных сетей и активного противодействия. Этот модуль описывает механизмы бесконфликтной репликации (CRDT), защищённый gossip-протокол, и византийский консенсус `D2BFT` (Dual Byzantine Fault Tolerance) для критических решений, затрагивающих HardState.

---

## 1. CRDT / IPFS / libp2p Fabric

### 1.1. Бесконфликтная репликация графа знаний

Рой использует комбинацию технологий для синхронизации состояния:

- **Yjs + CRDT** — совместное редактирование графа знаний и метаданных.
- **IPFS** — распространение артефактов (снапшоты L3, дистиллированные модели).
- **libp2p gossipsub** — peer discovery и маршрутизация обновлений.
- **Векторные часы** — разрешение конфликтов в метаданных Mem0g.

### 1.2. Каноническая структура CRDT-объекта

```json
{
  "schema_version": "2.0",
  "object_id": "uuid-1234",
  "type": "KnowledgeNode",
  "content": {
    "statement": "Use async for I/O-bound operations",
    "embedding": [0.1, 0.2, ...]
  },
  "metadata": {
    "vector_clock": {"node_A": 5, "node_B": 3},
    "timestamp": "2026-04-20T12:00:00Z",
    "creator": "node_A",
    "signature": "ed25519:..."
  },
  "links": [
    {"target": "uuid-5678", "type": "derived_from"}
  ]
}
```

## 2. Signed Gossip и синхронизация

### 2.1. Структура gossip-сообщения

```rust
struct GossipMessage {
    message_id: [u8; 32], // BLAKE3 хеш содержимого
    prev_message_id: Option<[u8; 32]>, // для каузальности
    topic: String,
    payload: Vec<u8>,
    timestamp: u64,
    ttl: u32,
    creator_id: String,
    signature: Vec<u8>, // Ed25519
}
```

### 2.2. Защита от подделки и спама

· Все gossip-сообщения подписываются Ed25519 (или Dilithium5).
· Rate limiting через token bucket (5 сообщений/сек на узел).
· Ротация ключей каждые 30 дней. Старые публичные ключи хранятся в GlobalState.security_state.

### 2.3. Hierarchical Gossip with Adaptive Quorum

· Core Nodes обмениваются полным графом через BFT-консенсус.
· Regional Aggregators получают обновления от Core Nodes и ретранслируют их edge-узлам в своей зоне.
· Edge Nodes участвуют только в локальном gossip с агрегатором.

Adaptive Quorum: Для критических обновлений (HardState) требуемое число подтверждений вычисляется динамически на основе текущей репутации узлов:

```python
def adaptive_quorum(nodes: List[Node]) -> int:
    total_weight = sum(node.reputation_score for node in nodes)
    return max(3, int(0.67 * total_weight))
```

## 3. Swarm-BFT 2.0: Dual Byzantine Fault Tolerance (D2BFT)

### 3.1. Обоснование перехода

Классический Swarm-BFT (PBFT) обеспечивает надёжность до 1/3 византийских узлов, но его производительность (O(N²) сообщений) становится ограничивающим фактором при масштабировании. D2BFT демонстрирует способность противостоять до 40% вредоносных узлов и снижает задержку консенсуса на ~20% по сравнению с PBFT.

### 3.2. Архитектура D2BFT

D2BFT — двухэтапный протокол:

1. DBFT-фаза (Делегирование):
   · Из пула Core-узлов на основе репутации и стохастического алгоритма выбирается подгруппа валидаторов.
   · Размер подгруппы настраивается (validator_count = 7).
2. PBFT-фаза (Консенсус внутри подгруппы):
   · Выбранные валидаторы запускают облегчённый PBFT-подобный протокол для достижения окончательного соглашения.
   · Сложность коммуникации снижается до O(m²), где m << n.

### 3.3. Псевдокод ядра D2BFT

```rust
impl D2BFT {
    async fn run_round(&mut self, proposal: Proposal) -> Result<ConsensusResult, Error> {
        // 1. DBFT-фаза: Делегирование
        let validator_set = self.select_validators(
            &self.core_nodes, self.config.validator_count, &self.reputation_scores
        ).await?;

        // 2. PBFT-фаза: Быстрый консенсус внутри выбранной группы
        let leader = self.elect_leader(&validator_set);
        let pbft_result = self.run_pbft_round(leader, &validator_set, proposal).await?;

        // 3. Фиксация результата и обновление репутации
        if pbft_result.is_committed() {
            self.commit(proposal).await?;
            Ok(ConsensusResult::Committed)
        } else {
            Err(ConsensusError::CommitFailed)
        }
    }
}
```

### 3.4. Показатели эффективности

Метрика Swarm-BFT (старый) D2BFT (новый) Целевое улучшение
Макс. доля вредоносных узлов 33% 40% +7%
Задержка консенсуса (p95) 1.5 сек ~1.2 сек -20%
Сложность коммуникации O(n²) O(m²), m << n Значительное снижение

### 3.5. Конфигурация

```json
{
  "consensus": {
    "protocol": "d2bft",
    "validator_count": 7,
    "leader_rotation_interval": 60,
    "view_change_timeout_ms": 3000,
    "max_byzantine_faults": 0.40
  }
}
```

## 4. Интеграция с другими модулями

Модуль Характер связи
Swarm_Topology.md Топология определяет, какие узлы участвуют в BFT и gossip.
Reputation_and_Coordination.md Репутация используется для выбора валидаторов и Adaptive Quorum.
Memory_Hierarchy_Mem0g.md CRDT-граф — реализация распределённой памяти L2.
Stealth_and_C2.md Альтернативные транспорты (Nostr, WebRTC) для скрытой синхронизации.
Global_State_and_Decision_Pipeline.md HardState изменения проходят через D2BFT на этапе Governance.

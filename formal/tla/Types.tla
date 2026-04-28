---- MODULE Types ----
\* Общие типы данных для всех спецификаций BlackSwan
EXTENDS Naturals, Sequences, FiniteSets

\* Идентификаторы узлов и ресурсов
NodeID == 1..MaxNodes
ResourceID == 1..MaxResources

\* Типы состояния узла (из NodeLifecycle)
NodeState == { "booting", "active", "suspected", "dead", "spawning" }

\* Тип записи в GlobalState: CRDT-подобные регистры
RecordType == { "lww", "counter", "map" }

\* Действия узла в DecisionPipeline
ActionType == { "trade", "spore", "sting", "sleep", "observe" }

\* Базовый тип сообщения в EventBus
Message == [type : STRING, from : NodeID, payload : STRING]

\* Экономический баланс
Balance == [principal : Real, income : Real, burn : Real]

\* Агрегированное состояние роя
SwarmState == [
    active_nodes : SUBSET NodeID,
    global_resources : [NodeID -> Balance],
    shared_knowledge : STRING   \* упрощённо – строка
]

====
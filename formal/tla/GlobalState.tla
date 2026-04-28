---- MODULE GlobalState ----
\* Глобальное состояние роя с LWW-регистрами и счётчиками
EXTENDS Types, Constants, Strings

VARIABLES
    swarms,          \* Состояние каждого узла (SwarmState)
    messages,        \* Канал сообщений (sequence)
    clock            \* Локальные часы узлов [NodeID -> Int]

Init ==
    /\ swarms = [n \in NodeID |-> [active_nodes |-> {n},
                                   global_resources |-> [r \in ResourceID |-> [principal |-> 1000, income |-> 0, burn |-> 0]],
                                   shared_knowledge |-> ""]]
    /\ messages = <<>>
    /\ clock = [n \in NodeID |-> 0]

\* Обновление состояния узла (LWW-регистр для знаний)
UpdateKnowledge(node, new_knowledge) ==
    LET s = swarms[node] IN
    [s EXCEPT !.shared_knowledge = new_knowledge]

\* Узел отправляет своё состояние другому
SendState(src, tgt) ==
    LET payload = swarms[src].shared_knowledge IN
    messages' = Append(messages, [type |-> "state_sync", from |-> src, payload |-> payload])

\* Приём и слияние состояний (LWW – последняя запись побеждает по длине строки)
MergeState(rcv) ==
    \E msg \in messages:
        LET new_know = msg.payload IN
        IF StringLength(new_know) > StringLength(swarms[rcv].shared_knowledge) THEN
            swarms' = [swarms EXCEPT ![rcv].shared_knowledge = new_know]
        ELSE
            UNCHANGED swarms

\* Главный инвариант: все узлы в итоге согласованы
AllNodesConsistent ==
    \A n1, n2 \in NodeID:
        swarms[n1].shared_knowledge = swarms[n2].shared_knowledge

\* Инвариант: баланс узла никогда не уходит в минус
BalanceNonNegative ==
    \A n \in NodeID:
        \A r \in ResourceID:
            swarms[n].global_resources[r].principal >= 0

Next ==
    \E node \in NodeID:
        \/ UpdateKnowledge(node, "info_" \o ToString(clock[node]))
        \/ \E tgt \in NodeID \setminus {node}: SendState(node, tgt)
        \/ MergeState(node)

Spec == Init /\ [][Next]_<<swarms, messages, clock>>

====
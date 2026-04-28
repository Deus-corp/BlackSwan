---- MODULE GlobalState ----
EXTENDS Naturals, Integers, FiniteSets, TLC, Sequences

CONSTANTS
    MaxNodes,
    MaxResources,
    MaxClock   \* Ограничение на количество обновлений

NodeID == 1..MaxNodes
ResourceID == 1..MaxResources

VARIABLES
    swarms,
    messages,
    clock

Init ==
    /\ swarms = [n \in NodeID |->
         [ active_nodes |-> {n},
           global_resources |-> [r \in ResourceID |->
               [ principal |-> 1000,
                 income |-> 0,
                 burn |-> 0 ]],
           shared_knowledge |-> 0 ]]
    /\ messages = <<>>
    /\ clock = [n \in NodeID |-> 0]

\* Обновление знаний возможно только если clock[node] < MaxClock
UpdateKnowledge(node) ==
    /\ clock[node] < MaxClock
    /\ swarms' = [swarms EXCEPT ![node].shared_knowledge = clock[node] + 1]
    /\ clock' = [clock EXCEPT ![node] = clock[node] + 1]
    /\ messages' = messages

SendState(src, tgt) ==
    /\ swarms' = swarms
    /\ clock' = clock
    /\ messages' =
         Append(messages,
           [ type |-> "state_sync",
             from |-> src,
             to |-> tgt,
             payload |-> swarms[src].shared_knowledge ])

MergeState(rcv) ==
    \E i \in 1..Len(messages) :
      LET msg == messages[i] IN
        /\ msg.type = "state_sync"
        /\ swarms' =
             IF msg.payload > swarms[rcv].shared_knowledge
             THEN [swarms EXCEPT ![rcv].shared_knowledge = msg.payload]
             ELSE swarms
        /\ messages' = messages
        /\ clock' = clock

Next ==
    \/ \E node \in NodeID : UpdateKnowledge(node)
    \/ \E src \in NodeID : \E tgt \in NodeID \ {src} : SendState(src, tgt)
    \/ \E node \in NodeID : MergeState(node)

TypeOK ==
    /\ swarms \in [NodeID -> [active_nodes : SUBSET NodeID,
                              global_resources : [ResourceID -> [principal : Nat, income : Nat, burn : Nat]],
                              shared_knowledge : Nat]]
    /\ messages \in Seq([type : STRING, from : NodeID, to : NodeID, payload : Nat])
    /\ clock \in [NodeID -> Nat]

BalanceNonNegative ==
    \A n \in NodeID:
      \A r \in ResourceID:
        swarms[n].global_resources[r].principal >= 0

Spec == Init /\ [][Next]_<<swarms, messages, clock>>
Symmetry == Permutations(NodeID)
====
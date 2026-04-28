---- MODULE SporeProtocol ----
EXTENDS Types, Constants, Strings

VARIABLES
    swarms,          \* Состояние каждого узла
    messages,        \* Канал сообщений
    clock,           \* Локальные часы
    failed_nodes,    \* Мёртвые узлы
    spore_pool,      \* Споры, готовые к активации
    activation_timer \* Таймер до создания споры

InitSpore ==
    /\ swarms = [n \in NodeID |-> [active_nodes |-> {n},
                                   global_resources |-> [r \in ResourceID |-> [principal |-> 1000, income |-> 0, burn |-> 0]],
                                   shared_knowledge |-> ""]]
    /\ messages = <<>>
    /\ clock = [n \in NodeID |-> 0]
    /\ failed_nodes = {}
    /\ spore_pool = {}
    /\ activation_timer = 0

\* Узел отказывает
FailNode(node) ==
    LET s = swarms[node] IN
    IF s.active_nodes = {node} THEN
        /\ failed_nodes' = failed_nodes \cup {node}
        /\ swarms' = [swarms EXCEPT ![node].active_nodes = {}]
        /\ activation_timer' = SporeDelay
        /\ UNCHANGED <<messages, clock, spore_pool>>
    ELSE
        UNCHANGED <<swarms, failed_nodes, activation_timer, messages, clock, spore_pool>>

\* Таймер создания споры
CreateSporeIfNeeded ==
    IF activation_timer > 0 THEN
        /\ activation_timer' = activation_timer - 1
        /\ IF activation_timer' = 0 THEN
            LET new_id = CHOOSE n \in NodeID \setminus (active_nodes \union failed_nodes): TRUE
            IN
                /\ new_id \notin failed_nodes
                /\ swarms' = [swarms EXCEPT ![new_id] = [active_nodes |-> {new_id},
                                                           global_resources |-> swarms[MinNode].global_resources,
                                                           shared_knowledge |-> swarms[MinNode].shared_knowledge]]
                /\ spore_pool' = spore_pool \cup {new_id}
                /\ UNCHANGED <<messages, clock, failed_nodes>>
        ELSE
            UNCHANGED <<swarms, spore_pool, activation_timer, messages, clock, failed_nodes>>
    ELSE
        UNCHANGED <<swarms, failed_nodes, activation_timer, spore_pool, messages, clock>>

\* Активация споры (становится активным узлом)
ActivateSpore ==
    \E node \in spore_pool:
        /\ spore_pool' = spore_pool \ {node}
        /\ swarms' = [swarms EXCEPT ![node].active_nodes = {node}]
        /\ failed_nodes' = failed_nodes \ {node}
        /\ UNCHANGED <<messages, clock, activation_timer>>

\* Действие по умолчанию: обычная активность (без изменений)
NormalStep ==
    UNCHANGED <<swarms, messages, clock, failed_nodes, spore_pool, activation_timer>>

NextSpore ==
    \/ \E node \in NodeID: FailNode(node)
    \/ CreateSporeIfNeeded
    \/ ActivateSpore
    \/ NormalStep

\* Свойство безопасности: рой никогда не вымирает полностью
SwarmNeverExtinct ==
    \/ (\E n \in NodeID: swarms[n].active_nodes /= {})
    \/ spore_pool /= {}
    \/ activation_timer > 0

SpecSpore == InitSpore /\ [][NextSpore]_<<swarms, messages, clock, failed_nodes, spore_pool, activation_timer>>

====
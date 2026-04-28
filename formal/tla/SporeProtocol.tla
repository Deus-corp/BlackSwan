---- MODULE SporeProtocol ----
EXTENDS Types, Constants, GlobalState

\* Дополнительные переменные для протокола спор
VARIABLES
    failed_nodes,      \* Множество узлов, считающихся мёртвыми
    spore_pool,        \* Узлы-споры, готовые к активации
    activation_timer   \* Таймер для отложенного создания спор

InitSpore ==
    /\ failed_nodes = {}
    /\ spore_pool = {}
    /\ activation_timer = 0

\* Узел отказывает
FailNode(node) ==
    LET s = swarms[node] IN
    IF s.active_nodes = {node} THEN
        /\ failed_nodes' = failed_nodes \cup {node}
        /\ swarms' = [swarms EXCEPT ![node].active_nodes = {}]
        /\ activation_timer' = SporeDelay   \* запускаем таймер споры
    ELSE
        UNCHANGED <<swarms, failed_nodes, activation_timer>>

\* Создание новой споры взамен умершего
CreateSporeIfNeeded ==
    IF activation_timer > 0 THEN
        /\ activation_timer' = activation_timer - 1
        /\ IF activation_timer' = 0 THEN
            \* Выбираем новый ID (просто минимальный неиспользуемый)
            LET new_id = CHOOSE n \in NodeID \setminus (active_nodes union failed_nodes): TRUE
            IN
                /\ new_id \notin failed_nodes
                /\ swarms' = [swarms EXCEPT ![new_id] = [active_nodes |-> {new_id},
                                                           global_resources |-> swarms[MinNode].global_resources,
                                                           shared_knowledge |-> swarms[MinNode].shared_knowledge]]
                /\ spore_pool' = spore_pool \cup {new_id}
        ELSE
            UNCHANGED <<swarms, spore_pool, activation_timer>>
    ELSE
        UNCHANGED <<swarms, failed_nodes, activation_timer>>

\* Активация споры (переход в активный рой)
ActivateSpore ==
    \E node \in spore_pool:
        /\ spore_pool' = spore_pool \ {node}
        /\ swarms' = [swarms EXCEPT ![node].active_nodes = {node}]
        /\ failed_nodes' = failed_nodes \ {node}

\* Свойство безопасности: рой никогда не вымирает полностью (есть хотя бы один активный узел)
SwarmNeverExtinct ==
    \A node \in NodeID: (swarms[node].active_nodes /= {}) \/ (spore_pool /= {}) \/ (activation_timer > 0)

NextSpore ==
    \E node \in NodeID:
        \/ FailNode(node)
        \/ CreateSporeIfNeeded
        \/ ActivateSpore

SpecSpore == InitSpore /\ [][NextSpore]_<<swarms, failed_nodes, spore_pool, activation_timer>>

====
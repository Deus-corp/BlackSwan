---- MODULE SporeProtocol ----
EXTENDS Naturals, Integers, FiniteSets, TLC, Sequences

CONSTANTS
    MaxNodes,
    MaxResources,
    MaxFailures,
    SporeDelay,
    MaxClock

NodeID == 1..MaxNodes
ResourceID == 1..MaxResources

VARIABLES
    swarms,
    messages,
    clock,
    failed_nodes,
    spore_pool,
    activation_timer

ActiveNodes == {n \in NodeID : swarms[n].active_nodes /= {}}
AvailableSporeNodes == NodeID \ (ActiveNodes \cup failed_nodes \cup spore_pool)

InitSpore ==
    /\ swarms = [n \in NodeID |->
         [ active_nodes |-> {n},
           global_resources |-> [r \in ResourceID |->
               [ principal |-> 1000,
                 income |-> 0,
                 burn |-> 0 ]],
           shared_knowledge |-> 0 ]]
    /\ messages = <<>>
    /\ clock = [n \in NodeID |-> 0]
    /\ failed_nodes = {}
    /\ spore_pool = {}
    /\ activation_timer = 0

FailNode(node) ==
    /\ node \in NodeID
    /\ node \notin failed_nodes
    /\ swarms[node].active_nodes /= {}
    /\ Cardinality(failed_nodes) < MaxFailures
    /\ failed_nodes' = failed_nodes \cup {node}
    /\ swarms' = [swarms EXCEPT ![node].active_nodes = {}]
    /\ activation_timer' = SporeDelay
    /\ UNCHANGED <<messages, clock, spore_pool>>

CreateSporeIfNeeded ==
    \/ /\ activation_timer > 0
       /\ activation_timer' = activation_timer - 1
       /\ activation_timer' > 0
       /\ UNCHANGED <<swarms, messages, clock, failed_nodes, spore_pool>>
    \/ /\ activation_timer > 0
       /\ activation_timer' = activation_timer - 1
       /\ activation_timer' = 0
       /\ AvailableSporeNodes /= {}
       /\ \E new_id \in AvailableSporeNodes :
            /\ swarms' =
                 [swarms EXCEPT ![new_id] =
                     [ active_nodes |-> {new_id},
                       global_resources |-> [r \in ResourceID |->
                           [ principal |-> 1000,
                             income |-> 0,
                             burn |-> 0 ]],
                       shared_knowledge |-> 0 ]]
            /\ spore_pool' = spore_pool \cup {new_id}
            /\ UNCHANGED <<messages, clock, failed_nodes>>
    \/ /\ activation_timer = 0
       /\ UNCHANGED <<swarms, messages, clock, failed_nodes, spore_pool, activation_timer>>

ActivateSpore ==
    \E node \in spore_pool:
        /\ spore_pool' = spore_pool \ {node}
        /\ swarms' = [swarms EXCEPT ![node].active_nodes = {node}]
        /\ failed_nodes' = failed_nodes \ {node}
        /\ UNCHANGED <<messages, clock, activation_timer>>

NormalStep ==
    /\ UNCHANGED <<swarms, messages, clock, failed_nodes, spore_pool, activation_timer>>

NextSpore ==
    \/ \E node \in NodeID : FailNode(node)
    \/ CreateSporeIfNeeded
    \/ ActivateSpore
    \/ NormalStep

\* Это свойство лучше проверять отдельно, а не как обязательный инвариант,
\* потому что при некоторых траекториях оно может нарушаться.
SwarmNeverExtinct ==
    ActiveNodes /= {} \/ spore_pool /= {} \/ activation_timer > 0

SpecSpore ==
    InitSpore /\ [][NextSpore]_<<swarms, messages, clock, failed_nodes, spore_pool, activation_timer>>
====
---- MODULE D2BFT ----
EXTENDS Naturals, Integers, FiniteSets, TLC

CONSTANTS
    Nodes,
    Corr,
    Faulty,
    Committee,
    MaxRounds,
    Quorum,
    Leader

ASSUME Corr \subseteq Nodes
ASSUME Faulty \subseteq Nodes
ASSUME Corr \intersect Faulty = {}
ASSUME Corr \union Faulty = Nodes
ASSUME Committee \subseteq Corr
ASSUME Cardinality(Committee) = 2
ASSUME Leader \in Committee

VARIABLES
    step,      \* текущий шаг (0,1,2,3)
    decisions,
    votes,
    committed

Values == {0, 1, 2}
Nil == -1

Init ==
    /\ step = 0
    /\ decisions = [n \in Nodes |-> Nil]
    /\ votes = [n \in Nodes |-> Nil]
    /\ committed = FALSE

\* Шаг 1: лидер предлагает значение 1
Step1 ==
    /\ step = 0
    /\ votes' = [votes EXCEPT ![Leader] = 1]
    /\ decisions' = decisions
    /\ committed' = committed
    /\ step' = 1

\* Шаг 2: все корректные узлы комитета голосуют за предложение
Step2 ==
    /\ step = 1
    /\ votes' = [n \in Nodes |-> 
        IF n \in (Committee \intersect Corr) THEN 1 ELSE votes[n]]
    /\ decisions' = decisions
    /\ committed' = committed
    /\ step' = 2

\* Шаг 3: проверка кворума и фиксация решения
Step3 ==
    /\ step = 2
    /\ LET supporters == {n \in Committee \intersect Corr : votes[n] = 1} IN
        /\ Cardinality(supporters) >= Quorum
        /\ decisions' = [n \in Nodes |-> 
            IF n \in (Committee \intersect Corr) THEN 1 ELSE decisions[n]]
        /\ committed' = TRUE
        /\ votes' = votes
        /\ step' = 3

Next ==
    \/ Step1
    \/ Step2
    \/ Step3

Safety ==
    \A n1, n2 \in Corr:
        (decisions[n1] /= Nil /\ decisions[n2] /= Nil) => (decisions[n1] = decisions[n2])

Invariant == Safety

Spec == Init /\ [][Next]_<<step, decisions, votes, committed>>
====
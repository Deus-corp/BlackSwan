---- MODULE GeneticEngine ----
EXTENDS Naturals, Integers, FiniteSets, TLC

CONSTANTS
    MaxPop,
    MinPop,
    MaxGenerations,
    MutationMax,
    DiversityThreshold

ASSUME MaxPop \in Nat
ASSUME MinPop \in Nat
ASSUME MaxGenerations \in Nat
ASSUME MutationMax \in Nat
ASSUME DiversityThreshold \in Nat
ASSUME MaxPop >= 1
ASSUME MinPop >= 1
ASSUME MinPop <= MaxPop
ASSUME DiversityThreshold <= 100

VARIABLES
    pop,
    champion,
    challenger,
    gen

Vars == <<pop, champion, challenger, gen>>

MaxElem(S) ==
    CHOOSE x \in S : \A y \in S : x >= y

MinElem(S) ==
    CHOOSE x \in S : \A y \in S : x <= y

Diversity(p) ==
    IF Cardinality(p) > 0 THEN
        (100 * (MaxElem(p) - MinElem(p))) \div MaxElem(p)
    ELSE
        0

MutatedPop(f, delta) ==
    IF f + delta > 0 THEN
        (pop \ {f}) \cup {f + delta}
    ELSE
        pop \ {f}

CrossoverPop(f1, f2) ==
    (pop \ {f1, f2}) \cup { (f1 + f2) \div 2 }

Init ==
    /\ pop = 1..MaxPop
    /\ champion = MaxElem(pop)
    /\ challenger = 0
    /\ gen = 0

TypeOK ==
    /\ pop \subseteq Nat
    /\ pop /= {}
    /\ champion \in Nat
    /\ challenger \in Nat
    /\ gen \in Nat
    /\ Cardinality(pop) >= MinPop
    /\ Cardinality(pop) <= MaxPop
    /\ gen <= MaxGenerations

MutateStep ==
    /\ gen < MaxGenerations
    /\ \E f \in pop :
         \E delta \in -MutationMax..MutationMax :
           /\ MutatedPop(f, delta) /= {}
           /\ Cardinality(MutatedPop(f, delta)) >= MinPop
           /\ Cardinality(MutatedPop(f, delta)) <= MaxPop
           /\ Diversity(MutatedPop(f, delta)) >= DiversityThreshold
           /\ pop' = MutatedPop(f, delta)
           /\ champion' = MaxElem({champion} \cup MutatedPop(f, delta))
           /\ IF Cardinality(MutatedPop(f, delta)) > 1
              THEN challenger' = CHOOSE c \in MutatedPop(f, delta) \ {champion'} : TRUE
              ELSE challenger' = 0
           /\ gen' = gen + 1

CrossoverStep ==
    /\ gen < MaxGenerations
    /\ \E f1 \in pop :
         \E f2 \in pop :
           /\ f1 /= f2
           /\ CrossoverPop(f1, f2) /= {}
           /\ Cardinality(CrossoverPop(f1, f2)) >= MinPop
           /\ Cardinality(CrossoverPop(f1, f2)) <= MaxPop
           /\ Diversity(CrossoverPop(f1, f2)) >= DiversityThreshold
           /\ pop' = CrossoverPop(f1, f2)
           /\ champion' = MaxElem({champion} \cup CrossoverPop(f1, f2))
           /\ IF Cardinality(CrossoverPop(f1, f2)) > 1
              THEN challenger' = CHOOSE c \in CrossoverPop(f1, f2) \ {champion'} : TRUE
              ELSE challenger' = 0
           /\ gen' = gen + 1

Stop ==
    /\ gen = MaxGenerations
    /\ UNCHANGED Vars

Next ==
    \/ MutateStep
    \/ CrossoverStep
    \/ Stop
    \/ UNCHANGED Vars

DiversityPreserved ==
    Diversity(pop) >= DiversityThreshold

PopSizeBounded ==
    Cardinality(pop) >= MinPop /\ Cardinality(pop) <= MaxPop

ChampionMonotone ==
    champion >= MaxElem(pop)

Spec ==
    Init /\ [][Next]_Vars
====
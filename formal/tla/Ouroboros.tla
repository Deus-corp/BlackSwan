---- MODULE Ouroboros ----
EXTENDS Naturals, Integers, FiniteSets, TLC

CONSTANTS
    MaxPop,
    MaxGenerations,
    MutationMax,
    V_h

VARIABLES
    pop,
    gen,
    v_s,
    v_h_accum

Init ==
    /\ pop = 1..MaxPop
    /\ gen = 0
    /\ v_s = 0
    /\ v_h_accum = 0

TypeOK ==
    /\ pop \subseteq Nat
    /\ pop /= {}
    /\ gen \in Nat
    /\ v_s \in Nat
    /\ v_h_accum \in Nat
    /\ Cardinality(pop) <= MaxPop
    /\ gen <= MaxGenerations

MinOfSet(S) ==
    CHOOSE x \in S : \A y \in S : x <= y

NextGen ==
    /\ gen < MaxGenerations
    /\ \E f \in pop:
         \E delta \in -MutationMax..MutationMax:
           LET new_f ==
                 f + delta
               mutated_pop ==
                 IF new_f > 0 THEN
                   (pop \ {f}) \cup {new_f}
                 ELSE
                   IF Cardinality(pop) > 1 THEN
                     pop \ {f}
                   ELSE
                     pop
               selected_pop ==
                 IF Cardinality(mutated_pop) > 1 THEN
                   mutated_pop \ {MinOfSet(mutated_pop)}
                 ELSE
                   mutated_pop
           IN
             /\ selected_pop /= {}
             /\ pop' = selected_pop
             /\ gen' = gen + 1
             /\ IF new_f > f
                THEN /\ v_s' = v_s + 1
                     /\ v_h_accum' = v_h_accum
                ELSE /\ v_s' = v_s
                     /\ v_h_accum' = v_h_accum + 1

Stop ==
    /\ gen = MaxGenerations
    /\ UNCHANGED <<pop, gen, v_s, v_h_accum>>

Next ==
    \/ NextGen
    \/ Stop

OuroborosInvariant ==
    pop /= {}
    /\ v_s + v_h_accum = gen
    /\ gen <= MaxGenerations

Spec ==
    Init /\ [][Next]_<<pop, gen, v_s, v_h_accum>>
====
---- MODULE CuriosityEngine ----
EXTENDS Naturals, Integers, FiniteSets, TLC

CONSTANTS
    MaxHypotheses,
    MaxResources,
    ResourcePerHypothesis,
    SurpriseThreshold

VARIABLES
    hypotheses,
    resources,
    surprise

Vars == <<hypotheses, resources, surprise>>

Init ==
    /\ hypotheses = 0
    /\ resources = MaxResources
    /\ surprise = 0

TypeOK ==
    /\ hypotheses \in Nat
    /\ resources \in Nat
    /\ surprise \in Nat
    /\ hypotheses <= MaxHypotheses
    /\ resources <= MaxResources

CanProcessSurprise ==
    /\ surprise > SurpriseThreshold
    /\ hypotheses < MaxHypotheses
    /\ resources >= ResourcePerHypothesis

SurpriseStep ==
    \E s \in 1..10 :
        IF s <= SurpriseThreshold THEN
            /\ surprise' = s
            /\ UNCHANGED <<hypotheses, resources>>
        ELSE IF hypotheses < MaxHypotheses /\ resources >= ResourcePerHypothesis THEN
            \E n \in 1..(MaxHypotheses - hypotheses) :
                /\ n * ResourcePerHypothesis <= resources
                /\ hypotheses' = hypotheses + n
                /\ resources' = resources - n * ResourcePerHypothesis
                /\ surprise' = 0
        ELSE
            /\ surprise' = s
            /\ UNCHANGED <<hypotheses, resources>>

ExploreHypotheses ==
    /\ surprise <= SurpriseThreshold
    /\ hypotheses > 0
    /\ \E n \in 1..hypotheses:
        /\ n * ResourcePerHypothesis <= resources
        /\ hypotheses' = hypotheses - n
        /\ resources' = resources
        /\ surprise' = surprise

Idle ==
    /\ ~CanProcessSurprise
    /\ UNCHANGED Vars

Next ==
    \/ SurpriseStep
    \/ ExploreHypotheses
    \/ Idle

ResourcesNonNegative ==
    resources >= 0

HypothesesBounded ==
    hypotheses <= MaxHypotheses

HighSurpriseIsBlocked ==
    surprise > SurpriseThreshold => ~CanProcessSurprise

Spec ==
    Init /\ [][Next]_Vars
====
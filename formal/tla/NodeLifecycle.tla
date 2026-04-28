---- MODULE NodeLifecycle ----
EXTENDS Naturals, Integers, FiniteSets, TLC

CONSTANTS MaxBootAttempts, MaxUptime

VARIABLES state, bootCount, uptime

vars == <<state, bootCount, uptime>>

Init == 
    /\ state = "Bootstrap"
    /\ bootCount = 0
    /\ uptime = 0

BecomeAlive ==
    /\ state = "Bootstrap"
    /\ bootCount < MaxBootAttempts
    /\ state' = "Alive"
    /\ bootCount' = bootCount + 1
    /\ uptime' = uptime

Tick ==
    /\ state = "Alive"
    /\ uptime < MaxUptime
    /\ state' = "Alive"
    /\ bootCount' = bootCount
    /\ uptime' = uptime + 1

LastBreath ==
    /\ state = "Alive"
    /\ state' = "Dead"
    /\ UNCHANGED <<bootCount, uptime>>

Sting ==
    /\ state = "Alive"
    /\ state' = "Dead"
    /\ UNCHANGED <<bootCount, uptime>>

Die ==
    /\ (state = "Bootstrap" /\ bootCount >= MaxBootAttempts)
       \/ (state = "Alive" /\ uptime >= MaxUptime)
    /\ state' = "Dead"
    /\ UNCHANGED <<bootCount, uptime>>

Next ==
    \/ BecomeAlive
    \/ Tick
    \/ LastBreath
    \/ Sting
    \/ Die

Spec == Init /\ [][Next]_vars

\* Определения инвариантов
NoResurrection ==
    state = "Dead" => [] (state = "Dead")

BootLimitRespected ==
    bootCount <= MaxBootAttempts

AliveImpliesBooted ==
    state = "Alive" => bootCount > 0
====
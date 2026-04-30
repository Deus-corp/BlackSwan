---- MODULE AdaptiveMotivation ----
EXTENDS Naturals, Integers, FiniteSets, TLC

CONSTANTS
    MaxSteps,
    MaxDQ,
    CriticalDQ,
    LowCapitalThreshold,
    HighSurpriseThreshold

VARIABLES
    step,
    dq,
    liveness,
    capital,
    surprise,
    w_survival,
    w_capital,
    w_curiosity

Vars == <<step, dq, liveness, capital, surprise, w_survival, w_capital, w_curiosity>>

Clamp(x, lo, hi) ==
    IF x < lo THEN lo
    ELSE IF x > hi THEN hi
    ELSE x

Init ==
    /\ step = 0
    /\ dq = 0
    /\ liveness = 100
    /\ capital = 100
    /\ surprise = 0
    /\ w_survival = 60
    /\ w_capital = 20
    /\ w_curiosity = 20

TypeOK ==
    /\ step \in Nat
    /\ dq \in Nat
    /\ liveness \in Nat
    /\ capital \in Nat
    /\ surprise \in Nat
    /\ w_survival \in Nat
    /\ w_capital \in Nat
    /\ w_curiosity \in Nat
    /\ dq <= MaxDQ
    /\ liveness <= 100
    /\ capital <= 1000
    /\ surprise <= 10
    /\ w_survival + w_capital + w_curiosity = 100

Next ==
    \/ /\ step < MaxSteps
       /\ \E dq_delta \in -1..1:
          \E live_delta \in -1..1:
          \E cap_delta \in -5..10:
          \E surp_val \in 0..10:
            LET dq1 == Clamp(dq + dq_delta, 0, MaxDQ)
                live1 == Clamp(liveness + live_delta, 0, 100)
                cap1 == Clamp(capital + cap_delta, 0, 1000)
                surp1 == surp_val
            IN
              /\ step' = step + 1
              /\ dq' = dq1
              /\ liveness' = live1
              /\ capital' = cap1
              /\ surprise' = surp1
              /\ IF (dq1 >= CriticalDQ) \/ (live1 < 50) THEN
                    /\ w_survival' = 90
                    /\ w_capital' = 10
                    /\ w_curiosity' = 0
                 ELSE IF (surp1 > HighSurpriseThreshold) /\ (cap1 > LowCapitalThreshold) THEN
                    /\ w_survival' = 40
                    /\ w_capital' = 10
                    /\ w_curiosity' = 50
                 ELSE
                    /\ w_survival' = 60
                    /\ w_capital' = 20
                    /\ w_curiosity' = 20
    \/ /\ step = MaxSteps
       /\ UNCHANGED Vars

WeightsSumToOne ==
    w_survival + w_capital + w_curiosity = 100

SurvivalDominatesInCrisis ==
    (dq >= CriticalDQ \/ liveness < 50) => (w_survival >= 90)

Spec ==
    Init /\ [][Next]_Vars
====
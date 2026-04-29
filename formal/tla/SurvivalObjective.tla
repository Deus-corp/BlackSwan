---- MODULE SurvivalObjective ----
EXTENDS Naturals, Integers, FiniteSets, TLC

CONSTANTS
    MaxCapital,
    MaxDQ,
    CriticalDQ,
    TradeReward,
    TradeRisk,
    HideCost,
    HideEffect,
    ExpandCost,
    ExpandEffect

ASSUME MaxCapital \in Nat
ASSUME MaxDQ \in Nat
ASSUME CriticalDQ \in Nat
ASSUME TradeReward \in Nat
ASSUME TradeRisk \in Nat
ASSUME HideCost \in Nat
ASSUME HideEffect \in Nat
ASSUME ExpandCost \in Nat
ASSUME ExpandEffect \in Nat
ASSUME CriticalDQ <= MaxDQ

VARIABLES
    capital,
    dq,
    liveness,
    must_hide

Vars == <<capital, dq, liveness, must_hide>>

Init ==
    /\ capital = MaxCapital \div 2
    /\ dq = 0
    /\ liveness = 50
    /\ must_hide = FALSE

TypeOK ==
    /\ capital \in 0..MaxCapital
    /\ dq \in 0..MaxDQ
    /\ liveness \in 0..100
    /\ must_hide \in BOOLEAN

SafeSub(x, y) ==
    IF x >= y THEN x - y ELSE 0

HideModeConsistent ==
    must_hide = (dq >= CriticalDQ)

Trade ==
    /\ ~must_hide
    /\ capital + TradeReward <= MaxCapital
    /\ dq + TradeRisk <= MaxDQ
    /\ capital' = capital + TradeReward
    /\ dq' = dq + TradeRisk
    /\ liveness' = liveness
    /\ must_hide' = (dq' >= CriticalDQ)

Hide ==
    /\ capital' = SafeSub(capital, HideCost)
    /\ dq' = SafeSub(dq, HideEffect)
    /\ liveness' = liveness
    /\ must_hide' = (dq' >= CriticalDQ)

Expand ==
    /\ ~must_hide
    /\ capital >= ExpandCost
    /\ liveness + ExpandEffect <= 100
    /\ capital' = capital - ExpandCost
    /\ dq' = dq
    /\ liveness' = liveness + ExpandEffect
    /\ must_hide' = must_hide

Next ==
    \/ Trade
    \/ Hide
    \/ Expand

CapitalNonNegative ==
    capital >= 0

DQWithinBounds ==
    dq <= MaxDQ

LivenessBounded ==
    liveness <= 100

Spec ==
    Init /\ [][Next]_Vars
====
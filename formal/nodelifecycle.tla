---- MODULE NodeLifecycle ----
EXTENDS Naturals, TLC

CONSTANTS MaxBootAttempts, MaxUptime

VARIABLES state, bootCount, uptime

vars == <<state, bootCount, uptime>>

(* Состояния узла: Bootstrap, Alive, Dead *)
NodeStates == {"Bootstrap", "Alive", "Dead"}

(* Инициализация: узел пытается загрузиться *)
Init == 
    /\ state = "Bootstrap"
    /\ bootCount = 0
    /\ uptime = 0

(* Переход: успешная загрузка и переход в Alive *)
BecomeAlive ==
    /\ state = "Bootstrap"
    /\ bootCount < MaxBootAttempts
    /\ state' = "Alive"
    /\ bootCount' = bootCount + 1
    /\ uptime' = uptime

(* Переход: работа узла (инкремент времени жизни) *)
Tick ==
    /\ state = "Alive"
    /\ uptime < MaxUptime
    /\ state' = "Alive"
    /\ bootCount' = bootCount
    /\ uptime' = uptime + 1

(* Переход: "Last Breath" – контролируемое самоуничтожение *)
LastBreath ==
    /\ state = "Alive"
    /\ state' = "Dead"
    /\ UNCHANGED <<bootCount, uptime>>

(* Переход: "Sting" – реакция на угрозу, ведущая к смерти *)
Sting ==
    /\ state = "Alive"
    /\ state' = "Dead"
    /\ UNCHANGED <<bootCount, uptime>>

(* Переход: отказ при загрузке или исчерпание времени жизни *)
Die ==
    /\ (state = "Bootstrap" /\ bootCount >= MaxBootAttempts
        \/ state = "Alive" /\ uptime >= MaxUptime)
    /\ state' = "Dead"
    /\ UNCHANGED <<bootCount, uptime>>

(* Набор всех переходов *)
Next ==
    \/ BecomeAlive
    \/ Tick
    \/ LastBreath
    \/ Sting
    \/ Die

(* Спецификация *)
Spec == Init /\ [][Next]_vars

(* Инвариант 1: узел никогда не возвращается из мёртвого состояния *)
NoResurrection ==
    state = "Dead" => [] (state = "Dead")

(* Инвариант 2: счётчик загрузок не превышает лимита *)
BootLimitRespected ==
    bootCount <= MaxBootAttempts

(* Инвариант 3: если узел жив, то он точно загружался *)
AliveImpliesBooted ==
    state = "Alive" => bootCount > 0

====
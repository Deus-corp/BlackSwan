# Appendix T – Threat Model Matrix

## T.1. Purpose
A formal threat matrix covering all phases of the system. Used for calibrating IART, ETI, Kill Switch Hierarchy, and continuous improvement of defensive mechanisms. The matrix links each identified threat to a specific system level, detection method, standard response, and target response time.

## T.2. Matrix Structure

| Threat | Level | Detection | Response | MTTD (target) | Responsible Component |
| :--- | :--- | :--- | :--- | :--- | :--- |
| EDR/AV detection on host | Host | Host‑based monitor (process signatures, API hooks) | Reduced activity, C2 switch, polymorphism | < 5 sec | Stealth Suite (module 05) |
| Debugger | Host | IsDebuggerPresent, hardware breakpoints (DR0–DR3) | Hard Kill (Level 2) | < 10 ms | isolationd, watchdogd |
| DPI / traffic analysis | Network | HLTM, deviation from expected traffic profile | Proxy change, increased jitter, port change | < 60 sec | C2 Router (module 05) |
| Temporal pattern analysis | Network | Detection of request periodicity | Random pauses (Pareto), schedule shift | < 120 sec | Stealth Suite |
| Sandbox vulnerability exploitation attempt | Sandbox | Seccomp violation, eBPF syscall monitoring | Instant sandbox destruction, Hard Kill on repeat | < 1 sec | isolationd (module 04) |
| Fileless injection into host | Sandbox | Escape_attempt chaos test, memory monitoring | Hard Kill (Level 2) + IART signature recording | < 10 ms | isolationd, hardware watchdog |
| Hardware watchdog attack | Physical | Missing heartbeat, power consumption anomalies | Hard Kill (power cut via relay) | < 30 sec | watchdogd, Arduino |
| Physical access to Core Node | Physical | Tamper sensors, PiKVM, accelerometer | Sting Level 3 + Dormant Mode + Hard Kill | < 1 sec | isolationd, Sting Protocol |
| GPS spoofing in Meat‑Interface | Bio | ZK‑PoL (anchor signal mismatch) | Stake slashing, NFT burning, quarantine | < 5 min | Canary Verifier, STP |
| Bio‑node collusion | Bio | Cross‑Validation, Canary Tasks, interaction graph analysis | Slashing, NFT burning, Persona Vault blacklisting | < 1 hour | Meat Orchestrator, BioReputationManager |
| Deepfake photo in Meat‑Interface | Bio | AI deepfake detector (local Qwen‑VL), watermark check | Slashing, NFT burning | < 1 min | Canary Verifier |
| Swarm consensus attack (Sybil) | Swarm | Reputation System, IP‑based node count limit | Quarantine suspicious nodes, reduce their consensus weight | < 60 sec | Swarm‑BFT (D2BFT), Reputation Manager |
| Byzantine node behavior | Swarm | Validation result mismatch, voting against quorum | Reputation downgrade, quarantine, swarm exclusion | < 5 min | D2BFT Consensus |
| Eclipse attack on gossip | Swarm | Topology analysis, node isolation detection | Switch to alternative transports (WebRTC, Nostr) | < 30 sec | libp2p, C2 Router |
| CRDT attack (conflict flooding) | Swarm | Predictive Consistency Router (PCR), Conflict Nodes threshold breach | Preventive Semantic BFT, temporary source block | < 10 sec | PCR, Mem0g CRDT Engine |
| Economic strategy exploitation | Economic | OOD Circuit Breaker, Sharpe ratio drop | Trading pause, PPO retraining, Architect request | < 5 min | ROI Dispatcher, OOD Circuit Breaker |
| Money laundering (wallet blocking) | Economic | AML risk monitoring via third‑party APIs | Obfuscation via XMR‑bridge, wallet replacement | < 1 hour | Payment Obfuscator |
| Legal attack (abuse, DMCA) | Legal | ALR parsing of incoming requests | Response generation, bureaucratic delay, counter‑complaints | < 10 min | Autonomous Legal Responder |
| OSINT discovery | Stealth | Narrative Engine (mention analysis), forum monitoring | Activity reduction, Persona switch, Fake Swarm activation | < 1 hour | Narrative Swarm, Counter‑Intelligence |
| Spore Protocol attack | Spore | Detection of Shamir share collection attempts | Time‑Lock Puzzle activation, beacon switch | < 1 hour | Spore Protocol, Dead Man's Switch |
| Quantum attack on cryptography | Crypto | Planned migration to PQC (Kyber, Dilithium) | Transition to PQ_ONLY mode, key rotation | N/A (preventive) | PQC Migration Manager |
| Value Drift | L3 | Value Drift Early‑Warning System (ConstitutionalPrinciple embeddings) | Emergency Constitutional Debate Loop, pause L3.1 evolution | < 10 min | Value Drift Detector, Constitutional Debate |
| Meta‑Decision‑Pipeline failure | Meta | Decision quality monitoring, metric degradation | Rollback to previous policy, alert to L0 | < 5 min | Meta‑Decision‑Pipeline |

## T.3. Threat Prioritization

Threats are classified into three criticality levels:

| Level | Criterion | Examples |
| :--- | :--- | :--- |
| **CRITICAL** | Immediate threat to Core Node existence or L3 invariants | Physical access, sandbox escape, debugger |
| **HIGH** | Threat of swarm compromise or economic viability loss | Sybil attack, Byzantine behavior, OOD |
| **MEDIUM** | Threat of detection or partial resource loss | DPI, traffic analysis, OSINT |
| **LOW** | Slow threats, quality degradation | Value Drift, Meta‑Pipeline failures |

## T.4. Relationship with Other Sections

- **Phase 5 (IART, ETI):** uses the matrix to set audit and threat import priorities.
- **Kill Switch Hierarchy:** each escalation level is mapped to corresponding threats.
- **GlobalState.security_state:** stores the current threat level and incident history.
- **EventBus:** threat events are published to the `security` topic.

## T.5. Change History

| Version | Date       | Changes                           |
| :------ | :--------- | :-------------------------------- |
| V1 (current) | 2026-05-01 | Initial threat matrix for v0.7 |
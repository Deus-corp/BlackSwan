# Cold Start Protocol

**Purpose:** Describe the procedure for automatically restoring the system from a completely powered-off state to full combat readiness. The protocol covers both a planned cold start (after manual Core Node power-on) and emergency awakening from Dormant Mode or recovery from Spore.

**Target time:** < 300 seconds until ready to make decisions via Fast Path.

---

## 1. Cold Start Stages

Power on → POST/BIOS → OS boot → systemd launches watchdogd → readiness checks → load GlobalState → start isolationd → start vLLM → Decision Pipeline active


### 1.1. Power On and Hardware Initialization (0–10 s)

- Motherboard performs POST. External Arduino Watchdog is registered from the start.
- Watchdog starts timer: if the first valid HMAC-heartbeat from the OS is not received within 120 seconds, Hard Kill occurs.

### 1.2. OS and System Daemons Boot (10–60 s)

- Minimal OS boot (read-only rootfs, all non-critical services disabled).
- systemd starts `watchdogd` — the first daemon that establishes UART communication with Arduino and begins sending heartbeats immediately after kernel load.

### 1.3. Readiness Checks (60–120 s)

The `readinessd` service performs a sequence of checks.

| # | Check              | Success Criteria                                    | Action on Failure                          |
| :--| :----------------- | :-------------------------------------------------- | :----------------------------------------- |
| 1 | **GPU detect**     | All expected GPUs visible in `nvidia-smi`           | Retry every 10 s, up to 5 attempts         |
| 2 | **Sandbox test**   | Kata Containers start with GPU passthrough < 500 ms | Fallback to gVisor (without GPU), Degraded Mode |
| 3 | **Network isolation**| All outgoing traffic except SOCKS5 blocked by nftables| Recheck rules, pause                    |
| 4 | **TEE attestation**| Trusted environment attestation valid               | Transition to DEGRADED, attempt re-attestation |
| 5 | **GlobalState restore**| Last snapshot from IPFS loaded and signatures valid| Attempt loading previous snapshot         |

### 1.4. GlobalState Load (120–150 s)

- The last valid `GlobalState` snapshot is loaded from IPFS.
- Core Node signatures are verified. On mismatch — restore from previous snapshot.
- `ConsistencyRouter` applies pending updates from EventBus (if network already available).

### 1.5. isolationd and vLLM Start (150–250 s)

- `isolationd` transitions to `INIT → VERIFIED → ARMED`.
- `vllm_launcher` starts DeepSeek-V4 instances with saved expert masks for `Vagrant` (20%) and `Arbtiragius` (30%).
- Inference check: test prompt → response < 200 ms.

### 1.6. Decision Pipeline Activation (250–300 s)

- `Decision Pipeline` switches to active mode.
- First cycle: analyze current state, apply urgent security updates.
- Core Node announces itself in the swarm (if phase ≥ 3) via Nostr Bridge.

---

## 2. Cold Start Modes

- **Hard Cold Start** – initiated after physical Hard Kill or prolonged power loss. All stages are performed, `GlobalState` restored from IPFS.
- **Warm Start** – initiated after software reboot without power loss. GPU and sandbox state preserved. Readiness Checks abbreviated. Time: < 90 s.
- **Recovery from Spore** – special mode initiated by `Spore Protocol`. Steps: Zombie Seed → MVS search → Core DNA Spore → full state and model load. Expected total recovery time: up to 24 hours.

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*
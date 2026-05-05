# Isolation & Sandbox Execution

**Purpose:** Describe the multi-layered system for isolating computational processes, formal security policies, a unified isolation control plane (Isolation Control Plane), and a hardware watchdog providing a physical protection layer. These mechanisms form the security foundation and operate continuously across all project phases — from the first Core Node boot to the global swarm.

---

## 1. Isolation architecture (Sandbox Layer)

Code execution isolation is implemented at several independent levels, in accordance with the **Defense in Depth** principle. Each level can be compromised only through a successful attack on the underlying layer.

| Level | Technology | Isolation principle | Cold start | GPU support | Use case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1 (primary)** | Kata Containers + QEMU | Hardware virtualization (KVM) + VFIO | 200–500 ms | Full (GPU passthrough) | Agent code execution |
| **2 (secrets)** | Firecracker | KVM + microVM | ~125 ms | Limited | Key management, HSM emulation |
| **3 (fast)** | gVisor (runsc) | Userspace kernel (Sentry) | <50 ms | Full | Fast validation iterations |

Each sandbox receives a unique identifier bound to the task and is completely destroyed after the execution cycle, guaranteeing no state preservation between tasks.

### 1.1. Kata Containers configuration with VFIO-passthrough

```toml
# /etc/kata-containers/configuration.toml
[hypervisor.qemu]
path = "/usr/bin/qemu-system-x86_64"
enable_vfio = true
vfio_device_sysfs_path = "/sys/bus/pci/devices/0000:01:00.0"
kernel_params = "intel_iommu=on iommu=pt"
```
Launching a sandbox with GPU passthrough:

```bash
docker run -d \
  --name agent_sandbox \
  --runtime=kata-runtime \
  --device=/dev/vfio/1:/dev/vfio/1 \
  --device=/dev/dri:/dev/dri \
  --network none \
  --memory="24g" \
  --cpus="8.0" \
  --read-only \
  --security-opt seccomp=/etc/swarm/sandbox_seccomp.json \
  -v /path/to/safe/workspace:/input:ro \
  -v /path/to/artefacts:/output \
  ipfs://QmPythonBaseImage
```

### 1.2. Species-Aware Sandboxing

The code executed in the sandbox inherits permissions and restrictions corresponding to the node species. For example:
Arbtiragius (30% experts) – network calls allowed strictly to specific financial protocol RPCs (Solana, Hyperliquid).
Sentinella (40% experts) – read-only access to system logs and eBPF monitoring allowed; network completely forbidden.
Architectus (60% experts) – compiler calls and access to test models allowed; network forbidden.
Vagrant (20% experts) – minimal profile, only code generation and validation.
Sandbox policies are overridden via species_mask in the X-Species-Mask header sent when starting a task.

## 2. Formal Isolation Policy Framework

In addition to technical layers, a formal policy is introduced to guarantee the principle of least privilege and protection against configuration errors.

### 2.1. Seccomp and AppArmor profiles

Seccomp profile (/etc/swarm/sandbox_seccomp.json):

```json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "architectures": ["SCMP_ARCH_X86_64"],
  "syscalls": [
    {
      "names": [
        "read", "write", "openat", "close", "fstat", "mmap",
        "munmap", "brk", "rt_sigaction", "rt_sigprocmask",
        "ioctl", "pread64", "pwrite64", "sched_yield", "futex",
        "epoll_create1", "epoll_ctl", "epoll_wait", "clone", "exit_group"
      ],
      "action": "SCMP_ACT_ALLOW"
    },
    {
      "names": ["bind", "connect", "sendto", "recvfrom", "socket"],
      "action": "SCMP_ACT_ERRNO"
    }
  ]
}
```

AppArmor profile for host protection of vLLM:

```text
profile vllm-sandbox flags=(attach_disconnected) {
  /var/lib/swarm/models/ r,
  /var/lib/swarm/workspace/ rw,
  /tmp/ rw,
  deny /etc/** w,
  deny /home/** rw,
  deny /root/** rw,
  network inet tcp,
  deny network inet tcp to 0.0.0.0/0,
  allow network inet tcp to 10.0.0.1:1080,
}
```

### 2.2. Immutable base images

All container images are built once, signed, and stored in IPFS. When the sandbox starts, the image hash is checked. On-the-fly modification is prohibited.

### 2.3. Egress Allowlist

Network access from the sandbox is only allowed to explicitly listed addresses via nftables:

```text
table inet filter {
    chain output {
        type filter hook output priority 0; policy drop;
        ip daddr 10.0.0.1 tcp dport 1080 accept  # SOCKS5 proxy
        ip daddr 192.168.1.100 accept              # local artifact repository
    }
}
```

### 2.4. Signed artifact chain

All input artifacts (code, prompts) must be signed. The sandbox verifies the signature before execution. Results are also signed with the sandbox key.

## 3. Isolation Control Plane

Isolation components (hardware watchdog, Kata sandbox, TEE attestation, network hygiene) can operate independently, creating a risk of desynchronization. The IsolationControlPlane introduces a unified state machine and health contract.

### 3.1. State machine

```text
INIT → VERIFIED → ARMED → RUNNING → KILL
  ↑                         │
  └─────────────────────────┘ (rollback on degradation)
                    │
                    └──→ DEGRADED (optional)
State	Description	Transition conditions
INIT	Initial state after power-on.	Automatically after host boot.
VERIFIED	Integrity check: SCV, TEE attestation, configurations.	All Readiness Checks passed.
ARMED	Sandbox created, GPU passed through, vLLM started, agent not active.	Sandbox starts successfully, network isolation active.
RUNNING	Agent executes the Ouroboros loop.	Heartbeats from sandbox and watchdog received regularly.
KILL	Critical isolation violation or watchdog command.	Escape attempt, SCV failure, heartbeat missing >30 s.
```

### 3.2. Unified Health Contract

All isolation subsystems publish status in JSON format, aggregated by the isolationd daemon (Rust, systemd service):

```json
{
  "timestamp": "2026-04-26T12:00:00Z",
  "state": "RUNNING",
  "components": {
    "sandbox": { "status": "ok", "container_id": "abc123", "gpu_passthrough": true, "fs_readonly": true },
    "tee": { "status": "ok", "attestation_valid": true, "measurement": "sha256:..." },
    "watchdog": { "status": "ok", "last_heartbeat": "2026-04-26T12:00:05Z", "temperature_c": 68 },
    "network": { "status": "ok", "egress_blocked": true, "proxy_alive": true }
  }
}
```

This contract is the single source of truth for the hardware watchdog.

### 3.3. isolationd implementation (pseudocode)

```rust
// isolationd/src/main.rs
enum IsolationState { Init, Verified, Armed, Running, Degraded, Kill }

struct IsolationControlPlane {
    sandbox_monitor: SandboxMonitor,
    tee_verifier: TEEVerifier,
    watchdog_channel: WatchdogUart,
}

impl IsolationControlPlane {
    async fn run(&mut self) {
        loop {
            let health = self.collect_health().await;
            let new_state = self.evaluate_transition(&health).await;
            if new_state == IsolationState::Kill {
                self.watchdog_channel.send_hard_kill("state_machine").await;
                break;
            }
            self.watchdog_channel.send_health_contract(&health).await;
        }
    }
}
```

## 4. Hardware watchdog and “Hard Kill” protocol

An external microcontroller (Arduino Uno R4 WiFi) is connected to the host via GPIO/UART and controls a power relay. It provides a physical layer of protection independent of the host's software state.

### 4.1. Load differentiation algorithm

The watchdog receives data from two sources:
Software heartbeat via UART with HMAC-SHA256 (sent by isolationd every 500 ms).
Current sensors INA219 on the 12V GPU/CPU power lines.
Legitimacy criterion: correlation between task type and GPU memory energy profile (VRAM load matches the structure of active expert mask weights).
Exploit Spike: characterized by a pulse freeze while maintaining high PCIe bus load or an anomalous power consumption pattern.

### 4.2. Extended PCIe Sideband Monitoring (SMBus)

The Arduino connects to the SMBus (pins B5, B6 of the PCIe slot) and monitors:
DMA activity: reading GPU status registers via SMBus. Abnormal activity during sandbox idle triggers Hard Kill.
PERST# signal (PCIe Reset): unauthorized GPU reset without OS command leads to immediate power off.
Correlation with INA219: matching power with bus activity to detect discrepancies.

Hardware implementation:

Arduino signal	Motherboard point	Purpose
A4 (SDA)	TPM Header (Pin 11)	SMBus data
A5 (SCL)	TPM Header (Pin 12)	SMBus clock
D2 (INT)	PCIe PERST# (Sideband)	Hardware bus reset detection
D3 (OUT)	Front Panel (PWR SW)	Soft-Kill
Relay Ctrl	ATX 24-pin (PS-ON)	Hard-Kill (physical disconnect)
Firmware logic (“Sentinel” algorithm) — three checks:

```cpp
if (current_draw > MAX_EXP_DRAW && heartbeat_status == EXPIRED) {
    trigger_airgap_relay(); // Physical disconnect
    log_to_external_eprom(CRITICAL_MALFUNCTION);
}
```

The full Arduino sketch with SMBus, INA219, and PERST# polling is provided in Appendix AD (planned).

## 5. Resource limits and Operational Guardrails

Hard limits prevent runaway processes and budget exhaustion.

Resource	Limit	Mechanism
CPU	8 cores per sandbox	--cpus="8.0" + cgroups
Memory	24 GB per sandbox	--memory="24g", OOM-killer
Disk	read-only rootfs, quota on /output	Docker volume
Network	none or via rate-limited proxy	nftables + token bucket
GPU Power	Limit on overheat	nvidia-smi -pl
API budget	
5
/
d
a
y
(
P
h
a
s
e
1
)
,
5/day(Phase1),20/day (Phase 2+)	Monitoring, auto-shutdown
Additional constraints:

Constraint	Value	Enforcement mechanism
Max risk per trade	2% of capital	Check in ROIDispatcher
Minimum coherence threshold	≥0.70	Forced pause and sleep_cycle_consolidation
Max iterations without progress	10	Runaway reasoning detection, forced sleep
Sandbox execution time	≤60 s	timeout in subprocess.run()
Max generated code size	10 000 tokens	Check in generate_controlled()
Forbidden code operations	os.system, subprocess.run, eval, exec	Static analysis before execution

## 6. Integration with other modules

Module	Connection
Hardware_Isolation.md	Describes initial isolation setup at Stage 0‑B. Readiness Checks.
Cold_Start_Protocol.md	Cold start introduces watchdogd and isolationd, checks sandbox.
Global_State_and_Decision_Pipeline.md	Isolation status stored in execution_state and security_state.
Event_Bus_and_Artifact_Model.md	Isolation events published to security topic. Readiness checks generate artifacts.
Stealth_and_C2.md	Network isolation and egress allowlist are part of the overall stealth strategy.
Operational_Security_IART.md	IART uses isolationd to run Red-Team attacks in a controlled environment.
Appendices/GPU_Configurations.md	Detailed hardware profiles for VFIO setup.
Appendices/Hardware_BOM.md	Full hardware specification, including watchdog.
Glossary.md	Definitions of Sandbox, VFIO, Hard Kill, TEE.
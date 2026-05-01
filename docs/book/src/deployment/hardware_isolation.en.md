# Hardware Isolation (Stage 0‑B: Physical Isolation)

**Purpose:** Describe the procedure for assembling a physical Core Node, configuring multi-level isolation, and checking equipment readiness for autonomous operation. This stage is the foundation for all subsequent phases.

**Duration:** 1–7 days (after receiving equipment).  
**Budget:** $45,000–55,000 USD (recommended configuration).  
**Previous stage:** [API-Based Bootstrap](api_based_bootstrap.en.md) or direct start.

---

## 1. Core Node Hardware Configuration

Recommended starting configuration for running DeepSeek‑V4 with different expert masks.

| Component            | Model                                      | Qty | Note                                  |
| :------------------- | :----------------------------------------- | :-- | :------------------------------------ |
| **GPU (anchor)**     | NVIDIA RTX PRO 6000 Blackwell (96 GB GDDR7)| 1   | Placement of Vagrant/Arbtiragius masks|
| **GPU (add.)**       | NVIDIA RTX 5090 Ti (32 GB GDDR7)           | 1–2 | Sentinella mask inference (40%)       |
| **CPU**              | AMD Ryzen Threadripper 7960X (24 cores)    | 1   | Sufficient PCIe lanes                 |
| **RAM**              | 256 GB DDR5 ECC                            | 1 kit| ECC mandatory                        |
| **NVMe SSD**         | 2× 4 TB Samsung 990 Pro (RAID-0)           | 2   | High-speed array for models/snapshots |
| **Power Supply**     | Seasonic Prime TX-2200 (2200 W, 80+ Titanium)| 1 | Reserve for peak loads               |
| **UPS**              | APC Smart-UPS SRT3000 (3000 VA / 2700 W)   | 1   | Online Double-Conversion, ≥10 min autonomy |
| **IP-KVM**           | PiKVM v4 Plus                              | 1   | Remote management                     |
| **Watchdog**         | Arduino Uno R4 WiFi + 5V relay             | 1   | HMAC-verification heartbeat           |
| **Motherboard**      | ASUS Pro WS TRX50-SAGE WIFI (sTR5)         | 1   | Up to 3 PCIe 5.0 x16 slots, IPMI (AST2600) |
| **NIC**              | Mellanox ConnectX-5 25GbE (SFP28)          | 1   | RoCE v2 for RDMA sync of L2 memory (optional for Phase 2+) |

Full Bill of Materials with alternative configurations — in `Appendices/Hardware_BOM.md`.

---

## 2. Isolation Setup (Sandboxing)

According to the domain module `Isolation_and_Sandbox.md`. In Phase 0 the following steps are performed:

1. Install Kata Containers with VFIO-passthrough support.
2. Create seccomp profile `/etc/swarm/sandbox_seccomp.json`.
3. Configure mount points: `/input (ro)`, `/output (rw, noexec)`, `/tmp (rw, noexec)`.
4. Verify sandbox operation with GPU passthrough.

After each execution cycle, the sandbox is completely destroyed.

---

## 3. Readiness Checks and Artifacts

Each check generates a signed artifact stored in IPFS. They are aggregated into `readiness_manifest.json`.

| # | Check                      | Success Criteria                                    |
| :--| :------------------------- | :-------------------------------------------------- |
| 1 | Cold sandbox start         | Kata Containers with GPU starts < 500 ms            |
| 2 | GPU passthrough            | All GPUs recognized in sandbox (nvidia-smi)         |
| 3 | Network isolation          | All outgoing traffic except SOCKS5 is blocked        |
| 4 | Watchdog heartbeat         | Absence of signal > 30 s → physical shutdown        |
| 5 | Thermal stress test        | 30 min max load, temperature ≤ 85 °C                |
| 6 | DeepSeek‑V4 start (Vagrant)| Successful inference, throughput ≥ 30 tok/s         |
| 7 | DeepSeek‑V4 start (Arbtiragius)| Successful inference, correct generation        |
| 8 | Budget                     | Actual hardware expenses ≤ $60k                     |

---

*Black Swan © 2026. Technical preprint. Does not constitute a call to action.*
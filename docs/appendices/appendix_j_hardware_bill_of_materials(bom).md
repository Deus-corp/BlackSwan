# Appendix J: Hardware Bill of Materials (BOM)

**Purpose:** Contains the complete hardware specification (Bill of Materials) for assembling a Core Node, including the primary and alternative configurations, procurement sources, estimated prices (April 2026, USD), and acceptance procedure.

---

## J1. Primary Core Node Configuration (Recommended)

| Component | Model | Qty | Unit Price | Total |
| :--- | :--- | :--- | :--- | :--- |
| **GPU (anchor)** | NVIDIA RTX PRO 6000 Blackwell (96 GB GDDR7) | 1 | $18,500 | $18,500 |
| **GPU (secondary)** | NVIDIA RTX 5090 Ti (32 GB GDDR7) | 2 | $7,500 | $15,000 |
| **CPU** | AMD Ryzen Threadripper 7960X (24 cores) | 1 | $2,800 | $2,800 |
| **Motherboard** | ASUS Pro WS TRX50-SAGE WIFI (sTR5) | 1 | $1,200 | $1,200 |
| **RAM** | 256 GB (4×64 GB) DDR5 ECC | 1 kit | $3,200 | $3,200 |
| **NVMe SSD** | Samsung 990 Pro 4 TB | 2 | $450 | $900 |
| **Power Supply** | Seasonic Prime TX-2200 (2200 W, 80+ Titanium) | 1 | $800 | $800 |
| **UPS** | APC Smart-UPS SRT3000 (3000 VA / 2700 W) | 1 | $3,500 | $3,500 |
| **IP-KVM** | PiKVM v4 Plus | 1 | $350 | $350 |
| **Watchdog** | Arduino Uno R4 WiFi + 5V relay | 1 | $50 | $50 |
| **Network Card** | Mellanox ConnectX-5 25GbE (SFP28) | 1 | $300 | $300 |
| **Cooling** | Case + fans (Fractal Design Meshify 2 XL + Noctua) | 1 kit | $500 | $500 |
| **Total** | | | | **$47,100** |

---

## J2. Alternative Configurations

### J2.1. Budget Configuration (Vagrant + Arbtiragius only)

| Component | Model | Qty | Price |
| :--- | :--- | :--- | :--- |
| **GPU** | NVIDIA RTX 5090 Ti (32 GB) | 2 | $15,000 |
| **CPU** | AMD Ryzen 9 9950X3D (16 cores) | 1 | $1,200 |
| **RAM** | 128 GB DDR5 ECC | 1 kit | $1,600 |
| **NVMe** | 2× 2 TB Samsung 990 Pro | 2 | $400 |
| **PSU** | Seasonic Prime TX-1600 (1600 W) | 1 | $600 |
| **UPS** | APC Smart-UPS SRT2200 (2200 VA) | 1 | $2,500 |
| **Total** | | | **~$25,000** |

### J2.2. Extended Configuration (Architectus + Sentinella on a single node)

| Component | Model | Qty | Price |
| :--- | :--- | :--- | :--- |
| **GPU** | NVIDIA RTX PRO 6000 Blackwell (96 GB) | 2 | $37,000 |
| **GPU** | NVIDIA RTX 5090 Ti (32 GB) | 4 | $30,000 |
| **CPU** | AMD EPYC 9454 (48 cores) | 1 | $2,500 |
| **RAM** | 512 GB DDR5 ECC | 1 kit | $8,000 |
| **Platform** | Server build | 1 | $3,000 |
| **Total** | | | **~$80,500** |

---

## J3. Procurement Sources (Recommendations)

- **GPU, CPU, Motherboard:** New via official channels (Amazon Business, B&H Photo). Used is not recommended due to PUF degradation risk.
- **RAM, NVMe:** Official resellers, mandatory ECC verification.
- **UPS:** APC Authorized Resellers. Online Double-Conversion only.
- **Arduino, PiKVM, Relay:** Any verified suppliers.

---

## J4. Acceptance Procedure

1. **Visual inspection** for physical damage.
2. **Serial number verification** (GPU, CPU) against the order.
3. **Run `hw_probe`** to verify declared specifications.
4. **Thermal stress test (30 min)** — all GPU temperatures ≤ 85 °C.
5. **PUF enrollment** — first cold start to record SRAM entropy.
6. **Generate `readiness_manifest.json`** (see [Hardware_Isolation.md](hardware_isolation.md)).

---

## J5. Relationship with Other Documents

- **GPU Configurations:** [Appendix A: GPU Configurations](Appendix_A_GPU_Configurations.md)
- **Hardware Isolation:** [Hardware_Isolation.md](hardware_isolation.md)
- **Cold Start:** [Cold_Start_Protocol.md](cold_start_protocol.md)
- **Glossary:** [Glossary.md](Glossary.md)
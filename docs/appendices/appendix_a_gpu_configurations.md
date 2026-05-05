```markdown
# Appendix A: GPU Configurations & Hardware Profiles

**Purpose:** Contains reference GPU configurations for all node types (Core Node, Regional Aggregator, Edge Node), power profiles, thermal envelopes, and expert mask distribution for DeepSeek‑V4 by species. Used by `hw_probe`, `vllm_launcher`, and `isolationd` components.

---

## A1. Node Configurations by Role

### A1.1. Core Node (Full Profile)

| Component          | Model                         | Qty       | Key Characteristics                           |
| :----------------- | :---------------------------- | :-------- | :-------------------------------------------- |
| **Anchor GPU**     | NVIDIA RTX PRO 6000 Blackwell | 1         | 96 GB GDDR7, 600 W TDP, PCIe 5.0 x16          |
| **Secondary GPU**  | NVIDIA RTX 5090 Ti            | 1–2       | 32 GB GDDR7, 450 W TDP, PCIe 5.0 x16          |
| **CPU**            | AMD Ryzen Threadripper 7960X  | 1         | 24 cores, 48 threads, 128 PCIe lanes           |
| **RAM**            | 256 GB DDR5 ECC               | 1 kit     | ECC mandatory for bit‑error protection         |
| **NVMe**           | 2× 4 TB Samsung 990 Pro       | 2         | RAID‑0, 7450 MB/s read                         |
| **Power Supply**   | Seasonic Prime TX‑2200        | 1         | 2200 W, 80+ Titanium                          |
| **UPS**            | APC Smart‑UPS SRT3000         | 1         | 3000 VA / 2700 W, Online Double‑Conversion     |

### A1.2. Regional Aggregator (Cloud Profile)

| Component  | Model                | Characteristics                    |
| :--------- | :------------------- | :--------------------------------- |
| **GPU**    | NVIDIA A10 / RTX 4090| 24 GB VRAM, 150–300 W TDP         |
| **vCPU**   | 16–32 cores          | Provider‑dependent                |
| **RAM**    | 64–128 GB            |                                   |
| **NVMe**   | 500+ GB              |                                   |

### A1.3. Edge Node (Rentable / Lightweight Profile)

| Component  | Model                     | Characteristics                         |
| :--------- | :------------------------ | :-------------------------------------- |
| **GPU**    | RTX 4090 / RTX 5090 Ti    | 24–32 GB VRAM                          |
| **vCPU**   | 8–16 cores                | For validation and light inference tasks|
| **RAM**    | 32–64 GB                  |                                        |
| **NVMe**   | 100–250 GB ephemeral      |                                        |

---

## A2. DeepSeek‑V4 Expert Mask Distribution

| Species        | Active Expert Share | VRAM Estimate (no offload) | Recommended Hardware                |
| :------------- | :------------------ | :------------------------- | :---------------------------------- |
| **Vagrant**    | 20%                 | ~80 GB                     | 1× RTX 4090 / rented                |
| **Arbtiragius**| 30%                 | ~120 GB                    | 1× RTX 5090 Ti (32 GB) + CPU offload|
| **Sentinella** | 40%                 | ~160 GB                    | 2× RTX 5090 Ti or 1× RTX PRO 6000   |
| **Architectus**| 60%                 | ~240 GB                    | 2× RTX PRO 6000 or 4× RTX 5090 Ti   |
| **Custodian**  | 10–15%             | ~40–60 GB                  | 1× RTX 4090 / rented, CPU offload possible |

---

## A3. Power Profiles

### A3.1. NVIDIA RTX PRO 6000 Blackwell

| Mode               | Power Limit    | Performance | Use Case                                             |
| :----------------- | :------------- | :---------- | :--------------------------------------------------- |
| **Max Performance**| 600 W (stock)  | 100%        | `Architectus` strategic tasks, formal verification   |
| **Balanced**       | 450 W          | ~85%        | `Sentinella`, threat monitoring                      |
| **Eco**            | 300 W          | ~65%        | `Vagrant`, background tasks, evolution               |

### A3.2. NVIDIA RTX 5090 Ti

| Mode               | Power Limit    | Performance | Use Case                                         |
| :----------------- | :------------- | :---------- | :----------------------------------------------- |
| **Max Performance**| 450 W (stock)  | 100%        | `Arbtiragius`, high‑frequency trading            |
| **Balanced**       | 350 W          | ~85%        | `Vagrant`, validation                            |
| **Eco**            | 250 W          | ~65%        | Reconnaissance, pruning, batch tasks             |

---

## A4. Thermal Envelope

| Node                     | Max GPU Temp | Action at 75 °C                            | Action at 85 °C                            | Emergency Shutdown          |
| :----------------------- | :----------- | :----------------------------------------- | :----------------------------------------- | :-------------------------- |
| **Core Node (PRO 6000)** | 85 °C        | Fan 80%, Power Limit 450 W → 300 W         | Fan 100%, Power Limit 300 W → 250 W        | 95 °C → Hardware Kill       |
| **Core Node (5090 Ti)**  | 83 °C        | Fan 80%, Power Limit 450 W → 350 W         | Fan 100%, Power Limit 350 W → 250 W        | 95 °C → Hardware Kill       |
| **Edge Node (rented)**   | 85 °C        | Load reduction, notification               | Inference shutdown                         | Rental termination          |

Cooling management is handled by the `adjust_cooling` script (see [Hardware_Isolation.md](hardware_isolation.md)).

---

## A5. PCIe Sideband Monitoring (SMBus)

Extended PCIe Sideband monitoring via Arduino is used to detect hidden GPU attacks (see [Isolation_and_Sandbox.md](Isolation_and_Sandbox.md), section 4.2).

| Arduino Signal | Connection Point          | Purpose                              |
| :------------- | :------------------------ | :----------------------------------- |
| A4 (SDA)      | TPM Header (Pin 11)       | SMBus data                           |
| A5 (SCL)      | TPM Header (Pin 12)       | SMBus clock                          |
| D2 (INT)      | PCIe PERST# (Sideband)    | Unauthorized bus reset detection     |
| D3 (OUT)      | Front Panel (PWR SW)      | Soft‑Kill                            |
| Relay Ctrl    | ATX 24‑pin (PS‑ON)        | Hard‑Kill (physical disconnection)   |

---

## A6. Relationship with Other Documents

- **Cold Start:** [Cold_Start_Protocol.md](cold_start_protocol.md)
- **Isolation and Watchdog:** [Isolation_and_Sandbox.md](Isolation_and_Sandbox.md)
- **vLLM Launch:** [Appendix B: Launch Commands](./Appendix_B_Launch_Commands.md)
- **Hardware BOM:** [Appendix J: Hardware BOM](./Appendix_J_Hardware_BOM.md)
- **Glossary:** [Glossary.md](Glossary.md)
```
# Hardware Transition Plan (Migration to Local Hardware)

**Purpose:** Describe the automated procedure for gradually transitioning the system from using cloud APIs (DeepSeek API or decentralized ephemeral nodes) to fully local execution of DeepSeek‑V4 on dedicated physical hardware. The plan activates when economic and technical prerequisites are met and guarantees seamless migration without stopping critical functions.

**Previous stages:** [API-Based Bootstrap](api_based_bootstrap.en.md) or [Hardware Isolation](hardware_isolation.en.md) (if hardware already exists, the plan is not needed).  
**Target state:** `api_mode == false` (complete independence from external APIs).

---

## 1. Transition Stages

| Stage              | Trigger                                        | Actions                                            | Duration   |
| :----------------- | :--------------------------------------------- | :------------------------------------------------- | :--------- |
| **1. Monitoring**  | `hardware_fund ≥ $40,000`                      | Monitor DeepSeek‑V4 weight availability, evaluate server configurations, forecast costs. | Continuous |
| **2. Acquisition** | DeepSeek‑V4 weights published + `hardware_fund ≥ $45,000` | Automatic purchase of equipment via Meat‑Interface (if allowed) or operator notification. | 1–2 weeks  |
| **3. Staging**     | Equipment received and assembled               | Deploy Core Node with DeepSeek‑V4 in shadow mode alongside API. | 2–4 weeks  |
| **4. Cutover**     | Shadow metrics ≥ API metrics + `V_s > V_h` confirmed | Switch `Decision Pipeline` to local model, disable API. | 1 day      |
| **5. Decommission**| Stable operation 30+ days without fallbacks to API | Remove API keys from service, redistribute funds to `hardware_fund`. | 1 day      |

---

## 2. Target Server Specification

To fully replace the API, hardware capable of running DeepSeek‑V4 with 50–60% expert activation (Architectus mode) is required.

| Component       | Model                            | Qty | Estimated Cost     |
| :-------------- | :------------------------------- | :-- | :----------------- |
| **GPU**         | NVIDIA RTX PRO 6000 Blackwell (96 GB) | 2–4 | $32,000 – $42,000  |
| **CPU**         | AMD EPYC 9454 (48 cores)         | 1   | $2,500             |
| **RAM**         | 512 GB DDR5 ECC                  | 1 kit| $8,000            |
| **NVMe**        | 2× 4 TB Samsung PM9A3 (RAID 1)   | 2   | $1,200             |
| **Power Supply**| 2400W Platinum (redundant)       | 2   | $1,200             |
| **Total**       |                                  |     | **$45,000 – $55,000** |

---

## 3. Cold Start Procedure for Local Model

Upon receiving equipment, the script `cold_start_deepseek.sh` (artifact `QmColdStartDeepSeekV1`) is executed:

```bash
#!/bin/bash
# 1. Download DeepSeek-V4 weights from IPFS / official hub
# 2. Convert to vLLM format (AWQ quantization)
# 3. Launch vLLM server with expert masks for Architectus (60%) and Sentinella (40%)
# 4. Verify through Readiness Checks
# 5. Switch `GlobalState.api_mode = false`
```
Black Swan © 2026. Technical preprint. Does not constitute a call to action.
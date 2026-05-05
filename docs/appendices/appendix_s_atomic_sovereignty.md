# Appendix S — Atomic Sovereignty Specifications

## S.1. Purpose
Detailed technical requirements for hardware platforms that ensure
the physical sovereignty of the "Black Swan 03" system. These specifications
are used when deploying nodes of the `Architectus` and `Sentinella` species
in Phase 4.

## S.2. Reference Architecture of a RISC‑V Node
### S.2.1. Processor Core
- **ISA:** RV64GCB (with Bitmanip and Crypto extensions).
- **Number of cores:** ≥ 16.
- **Frequency:** ≥ 2.0 GHz.
- **Cache:** L1 64 KB (I/D), L2 1 MB per cluster, L3 32 MB shared.

### S.2.2. Compute Accelerator
- **Type:** RISC‑V Vector Extension (RVV 1.0) + custom matrix engine for tensor operations.
- **Performance:** ≥ 50 TOPS (INT8).

### S.2.3. Memory and Storage
- **RAM:** 128 GB DDR5 ECC (expandable up to 512 GB).
- **Storage:** 2× 4 TB NVMe SSD (RAID‑1) with hardware encryption (AES‑XTS).

### S.2.4. Security
- **PUF:** SRAM PUF or RO‑PUF for root key generation.
- **TEE:** Keystone Enclave (RISC‑V) or equivalent.
- **Watchdog:** External microcontroller with its own power supply.

##### S.2.4.1. Quantum‑Resistant Optical PUF (optional)
To protect against future quantum attacks on classical SRAM/RO‑PUFs (based on delay and start‑up state measurements), support for **optical PUFs** is introduced. An optical PUF uses laser scattering in an inhomogeneous transparent medium (e.g., a polymer with nanoparticles). The interference pattern (speckle) has an exponentially large number of degrees of freedom and **cannot be modeled even by a quantum computer** due to the computational complexity of solving the inverse scattering problem.

**Advantages:**
- **Quantum resistance:** the task of reconstructing the scatterer structure from a speckle pattern remains NP‑hard even for quantum algorithms.
- **Extreme sensitivity to tampering:** any physical access attempt to the chip irreversibly changes the microstructure of the medium, destroying the PUF.
- **High entropy:** up to 10^6 independent bits per mm².

**Integration with Core DNA:**
1. During manufacturing of the atomic node, the optical PUF is "burned" by a laser and sealed.
2. At initial initialization, the baseline speckle pattern is measured → `device_seed_opt = KDF(speckle_pattern, salt)`.
3. Core DNA is encrypted with a dual key: `K_dna = HKDF(device_seed_sram XOR device_seed_opt, “core_dna”)`. Both PUFs are required for decryption, further complicating attacks.
4. On every cold start, the optical PUF is re‑verified; a discrepancy > 0.1% → activation of Kill Switch Level 5.

**Hardware Implementation:**
- **Components:** miniature VCSEL laser, CMOS sensor, transparent polymer layer.
- **Cost:** adds ~$50 to the BOM of the atomic node.
- **HAL support:** the `opt_puf.ko` driver provides the `/dev/opt_puf` interface for reading raw speckle data.

**Configuration in `global_policy.json` (addition):**
```json
{
  "atomic_sovereignty": {
    "puf": {
      "type": "hybrid",
      "primary": "sram_puf",
      "secondary": "optical_puf",
      "optical_tolerance": 0.001
    }
  }
}
```

## S.3. PUF Integration with Core DNA
1. On first boot, the node measures the PUF response and generates `device_seed = KDF(PUF_response, salt)`.
2. Core DNA is encrypted with the key `K_dna = HKDF(device_seed, “core_dna”)`.
3. At every boot, the key is recomputed; if the PUF response has changed (e.g., the chip has been moved), decryption is impossible.

## S.4. Energy Autonomy
### S.4.1. Solar Controller
- **Model:** MPPT controller with Modbus interface.
- **Array power:** ≥ 3 kW (peak).
- **Batteries:** LiFePO4, capacity ≥ 10 kWh.

### S.4.2. Energy‑Saving Protocol
- The node receives weather forecasts via a LoRa gateway or satellite link.
- If low generation is predicted, non‑critical tasks are deferred.
- When the charge falls below 15%, the node enters `dormant` mode, maintaining only the watchdog timer and wake‑up receiver.

## S.5. Local Mesh Network
In the absence of global internet, atomic nodes communicate via:
- **LoRaWAN:** range up to 15 km, throughput up to 50 kbps.
- **Satellite terminals:** Iridium SBD / Starlink (backup).

## S.6. Relationship with Other Sections
- **Phase 4 (Physical Sovereignty):** site selection and deployment.
- **Module 04 (Isolation):** integration with the hardware watchdog.
- **Appendix Q (Cross‑Platform Toolchain):** building for RISC‑V.

## S.7. Change History
| Version | Date       | Changes                                 |
| :------ | :--------- | :-------------------------------------- |
| V1      | 2026-05-15 | Initial specification for v0.8          |

## S.8. DeepSeek‑V4 Local Deployment
### S.8.1. Network Requirements
An initial download of DeepSeek‑V4 weights (~500 GB in AWQ 4‑bit format) requires a high‑speed internet connection (≥ 1 Gbps). It is recommended to use IPFS for decentralized download and integrity verification. Weights CID: `QmDeepSeekV4Weights`.

### S.8.2. Quantization
To reduce VRAM requirements, **AWQ 4‑bit** quantization is used. Expected accuracy drop: ≤ 2% on code generation benchmarks. For `Architectus` mode (60% experts) ~240 GB VRAM is required; for `Vagrant` (20% experts) ~80 GB VRAM is sufficient.

### S.8.3. Expert Masks
The configuration of expert masks for each species is stored in `/etc/swarm/expert_masks/` and loaded when vLLM starts. Masks are signed with the Core Node key to prevent tampering. Dynamic mask switching is supported via the vLLM API (`/v1/expert_mask`).

### S.8.4. Utilization Monitoring
The `telemetryd` daemon tracks:
- GPU load for each card.
- Expert activation (via vLLM hooks).
- Temperature and power consumption.
If thresholds are exceeded, the number of active experts is automatically reduced (fallback mode).

### S.8.5. Local Execution on RISC‑V
For atomic nodes on the RISC‑V architecture, a lightweight build of vLLM with support for the RVV 1.0 vector extension is used. DeepSeek‑V4 weights are converted into a format compatible with the custom matrix engine. If performance is insufficient, the `Vagrant` mask (20% experts) is activated, allowing the node to maintain autonomy under limited resources.

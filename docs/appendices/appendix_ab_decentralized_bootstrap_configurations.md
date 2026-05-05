# Appendix AB: Decentralized Bootstrap Configuration Reference

**Purpose:** Contains reference configuration files, scripts, and code examples for implementing the decentralized system startup (Phase 0‑A). Includes an SDL file for deploying ephemeral inference nodes on Akash, a dynamic SDL generation script, post‑quantum protection (HPQC) configuration for Wasm relays (WER 2.0), and an example Wasm relay module with hybrid encryption.

---

## AB.1. Reference SDL File for Akash (Ephemeral Inference Node)

```yaml
version: "2.0"
services:
  inference-node:
    image: vllm/vllm-openai:latest
    expose:
      - port: 8000
        as: 8000
        to:
          - global: true
    env:
      - "MODEL=deepseek-ai/DeepSeek-V4-Distill-Qwen-32B"
      - "MAX_MODEL_LEN=4096"
      - "VLLM_GPU_MEMORY_UTILIZATION=0.9"
    command:
      - "python3"
      - "-m"
      - "vllm.entrypoints.openai.api_server"
      - "--model"
      - "$(MODEL)"
      - "--tensor-parallel-size"
      - "1"
profiles:
  compute:
    inference-node:
      resources:
        cpu:
          units: 8
        memory:
          size: 32Gi
        storage:
          size: 50Gi
        gpu:
          units: 1
          attributes:
            vendor:
              nvidia:
                - model: rtx4090
                - model: a100
deployment:
  inference-node:
    akash:
      profile: inference-node
      count: 1
```

---

## AB.2. Dynamic SDL Generation Script (Python)

```python
# scripts/generate_akash_sdl.py
import yaml
import random

regions = ["us-west", "eu-north", "ap-southeast"]
providers = ["akash1365n0x7dg87uaj...", "akash1xyz..."]

sdl = yaml.safe_load(open("base_sdl.yaml"))
sdl["profiles"]["compute"]["inference-node"]["resources"]["gpu"]["attributes"]["vendor"]["nvidia"]["model"] = random.choice(["rtx4090", "a100", "h100"])
sdl["deployment"]["inference-node"]["akash"]["signedBy"] = random.choice(providers)

yaml.dump(sdl, open("dynamic_deploy.yaml", "w"))
```

---

## AB.3. PQC Configuration for Wasm Relays (global_policy.json snippet)

```json
{
  "wer_pqc": {
    "enabled": true,
    "kem_algorithm": "Kyber768",
    "hybrid_mode": true,
    "classic_curve": "X25519",
    "key_rotation_interval_sec": 900,
    "overlap_window_packets": 100,
    "auto_destruct_on_idle_sec": 300
  }
}
```

---

## AB.4. Example Wasm Relay Module with HPQC (Rust, pseudocode)

```rust
// wer_relay/src/lib.rs
use pqcrypto_kyber::kyber768::*;
use x25519_dalek::{PublicKey, StaticSecret};

#[no_mangle]
pub extern "C" fn relay_packet(
    input_ptr: *const u8,
    input_len: usize,
    output_ptr: *mut u8,
    output_cap: usize,
) -> i32 {
    // Decrypt outer layer (AES-256-GCM, key derived via HPQC)
    let outer_key = derive_hybrid_key(session_kyber_sk, session_x25519_sk);
    let inner = aes_gcm_decrypt(input, outer_key);

    // Extract next hop and encrypted payload
    let (next_hop, payload) = parse_onion_packet(&inner);

    // Add jitter
    wait_jitter();

    // Forward
    if is_final_hop(next_hop) {
        forward_to_target(next_hop, payload)
    } else {
        forward_to_next_relay(next_hop, payload)
    }
}
```

---

## AB.5. Relationship with Other Documents

- WER 2.0 and HPQC: [Stealth_and_C2.md](Stealth_and_C2.md)
- Decentralized Bootstrap (Phase 0‑A): [API_Based_Bootstrap.md](API_Based_Bootstrap.md)
- Launch scripts: Appendix B: Launch Commands
- Main configuration: Appendix L: Configuration Files
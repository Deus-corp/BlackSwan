# Appendix AB: Decentralized Bootstrap Configuration Reference

**Назначение:** Содержит эталонные конфигурационные файлы, скрипты и примеры кода для реализации децентрализованного старта системы (Phase 0‑A). Включает SDL‑файл для развёртывания эфемерных инференс‑узлов на Akash, скрипт динамической генерации SDL, конфигурацию постквантовой защиты (HPQC) для Wasm‑релеев (WER 2.0) и пример Wasm‑модуля релея с гибридным шифрованием.

---

## AB.1. Эталонный SDL‑файл для Akash (Ephemeral Inference Node)

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

## AB.2. Скрипт генерации динамического SDL (Python)

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

## AB.3. Конфигурация PQC для Wasm‑релеев (фрагмент global_policy.json)

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

## AB.4. Пример Wasm‑модуля релея с HPQC (Rust, псевдокод)

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
    // Дешифровка внешнего слоя (AES-256-GCM, ключ получен через HPQC)
    let outer_key = derive_hybrid_key(session_kyber_sk, session_x25519_sk);
    let inner = aes_gcm_decrypt(input, outer_key);

    // Извлечение следующего хопа и шифрованного payload
    let (next_hop, payload) = parse_onion_packet(&inner);

    // Добавление jitter
    wait_jitter();

    // Пересылка
    if is_final_hop(next_hop) {
        forward_to_target(next_hop, payload)
    } else {
        forward_to_next_relay(next_hop, payload)
    }
}
```

---

## AB.5. Связь с другими документами

· WER 2.0 и HPQC: Stealth_and_C2.md
· Decentralized Bootstrap (Phase 0‑A): API_Based_Bootstrap.md
· Скрипты запуска: Appendix B: Launch Commands
· Основная конфигурация: Appendix L: Configuration Files
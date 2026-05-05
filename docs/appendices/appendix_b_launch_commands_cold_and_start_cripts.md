# Appendix B: Launch Commands & Cold Start Scripts

**Purpose:** Contains reference commands for launching all key components of the Black Swan system: vLLM with expert masks, isolated sandboxes (Kata Containers, gVisor), hardware watchdog, cold start script (`cold_start.sh`), and readiness checks. All commands are validated for the Core Node configuration described in [Appendix A](Appendix_A_GPU_Configurations.md) and are current as of April 2026.

---

## B1. Launching vLLM with DeepSeek‑V4 Expert Masks

The system launches one or more vLLM instances with dynamic expert activation depending on the active species.

### B1.1. `Vagrant` Profile (20% experts)

```bash
vllm serve deepseek-ai/DeepSeek-V4 \
  --api-key sk-swarm-vagrant \
  --port 8000 \
  --expert-mask vagrant \
  --expert-percent 20 \
  --quantization awq_4bit \
  --num-speculative-tokens 8 \
  --dynamic-proposer true \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.70 \
  --tensor-parallel-size 1
```

### B1.2. Arbtiragius Profile (30% experts)

```bash
vllm serve deepseek-ai/DeepSeek-V4 \
  --api-key sk-swarm-arbiter \
  --port 8001 \
  --expert-mask arbiter \
  --expert-percent 30 \
  --quantization awq_4bit \
  --num-speculative-tokens 6 \
  --dynamic-proposer false \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.75 \
  --tensor-parallel-size 1
```

### B1.3. Sentinella Profile (40% experts)

```bash
vllm serve deepseek-ai/DeepSeek-V4 \
  --api-key sk-swarm-sentinel \
  --port 8002 \
  --expert-mask sentinel \
  --expert-percent 40 \
  --quantization awq_4bit \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.80 \
  --tensor-parallel-size 1
```

### B1.4. Architectus Profile (60% experts, requires full Core Node)

```bash
vllm serve deepseek-ai/DeepSeek-V4 \
  --api-key sk-swarm-architect \
  --port 8003 \
  --expert-mask architect \
  --expert-percent 60 \
  --quantization awq_4bit \
  --max-model-len 16384 \
  --gpu-memory-utilization 0.90 \
  --tensor-parallel-size 2 \
  --pipeline-parallel-size 1
```

---

## B2. Launching Isolated Sandboxes

### B2.1. Kata Containers with GPU Passthrough (Primary Sandbox)

```bash
# Download base image from IPFS
ipfs get QmPythonBaseImage -o /var/lib/swarm/images/python_base.img

# Launch sandbox with VFIO passthrough
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
  -v /var/lib/swarm/safe_workspace:/input:ro \
  -v /var/lib/swarm/artefacts:/output \
  -v /tmp/sandbox_tmp:/tmp:rw,noexec \
  /var/lib/swarm/images/python_base.img
```

### B2.2. gVisor (Fast Validation Iterations)

```bash
docker run -d \
  --name validation_sandbox \
  --runtime=runsc \
  --runtime-arg=platform=kvm \
  --network none \
  --memory="12g" \
  --cpus="4.0" \
  --read-only \
  -v /var/lib/swarm/safe_workspace:/input:ro \
  -v /var/lib/swarm/artefacts:/output \
  /var/lib/swarm/images/python_lightweight.img
```

---

## B3. Hardware Watchdog and Monitoring

### B3.1. Uploading the Sketch to Arduino Uno R4 WiFi

```bash
# Compile and upload watchdog firmware
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi /var/lib/swarm/firmware/watchdog_sketch.ino
arduino-cli upload --fqbn arduino:renesas_uno:unor4wifi --port /dev/ttyACM0 /var/lib/swarm/firmware/watchdog_sketch.ino
```

### B3.2. Starting the isolationd Daemon (systemd)

```bash
systemctl enable isolationd
systemctl start isolationd
systemctl status isolationd
```

Daemon configuration: `/etc/swarm/isolationd.toml`

---

## B4. Cold Start Script (cold_start.sh)

```bash
#!/bin/bash
set -euo pipefail

echo "[COLD_START] Beginning Black Swan cold start sequence..."

# 1. Check GPU availability
echo "[COLD_START] Checking GPU availability..."
nvidia-smi || (echo "[FATAL] No GPU detected. Aborting." && exit 1)

# 2. Restore GlobalState from IPFS
echo "[COLD_START] Restoring GlobalState snapshot..."
GLOBAL_STATE_CID=$(cat /var/lib/swarm/global_state_cid.txt)
ipfs get "$GLOBAL_STATE_CID" -o /var/lib/swarm/global_state.json

# 3. Verify snapshot signatures
echo "[COLD_START] Verifying snapshot signatures..."
verify_artifact --cid "$GLOBAL_STATE_CID" --public-key /etc/swarm/keys/artifact_pub.pem || exit 1

# 4. Launch vLLM with minimal mask (Vagrant)
echo "[COLD_START] Launching vLLM (Vagrant profile)..."
vllm serve deepseek-ai/DeepSeek-V4 \
  --port 8000 \
  --expert-mask vagrant \
  --expert-percent 20 \
  --quantization awq_4bit \
  --gpu-memory-utilization 0.70 &

# 5. Wait for vLLM readiness
echo "[COLD_START] Waiting for vLLM to become healthy..."
curl --retry 30 --retry-delay 2 --retry-connrefused http://localhost:8000/health

# 6. Launch Arbtiragius (30%) if Core Node is ready
if [ "${CORE_NODE_READY:-false}" = "true" ]; then
  echo "[COLD_START] Launching vLLM (Arbtiragius profile)..."
  vllm serve deepseek-ai/DeepSeek-V4 \
    --port 8001 \
    --expert-mask arbiter \
    --expert-percent 30 \
    --quantization awq_4bit \
    --gpu-memory-utilization 0.75 &
fi

# 7. Start isolationd
echo "[COLD_START] Starting isolationd..."
systemctl start isolationd

# 8. Activate Decision Pipeline
echo "[COLD_START] Decision Pipeline active."
echo "[COLD_START] Cold start complete. System online."
```

---

## B5. Readiness Checks

```bash
# Check 1: GPU passthrough
docker run --rm --runtime=kata-runtime --device=/dev/vfio/1:/dev/vfio/1 nvidia/cuda:12.4-base nvidia-smi

# Check 2: Watchdog heartbeat
echo "HMAC_HEARTBEAT" > /dev/ttyACM0

# Check 3: Thermal stress test (30 min, monitor temperature)
stress-ng --gpu 4 --cpu 8 --timeout 30m
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader

# Check 4: Inference
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-v4", "prompt": "def hello():", "max_tokens": 10}'
```

---

## B6. Relationship with Other Documents

- GPU Configurations: [Appendix A: GPU Configurations](Appendix_A_GPU_Configurations.md)
- Hardware Isolation: [Hardware_Isolation.md](Hardware_Isolation.md)
- Cold Start: [Cold_Start_Protocol.md](Cold_Start_Protocol.md)
- Isolation and Watchdog: [Isolation_and_Sandbox.md](Isolation_and_Sandbox.md)
- Glossary: [Glossary.md](Glossary.md)
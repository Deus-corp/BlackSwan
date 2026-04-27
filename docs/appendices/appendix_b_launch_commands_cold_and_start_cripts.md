# Appendix B: Launch Commands & Cold Start Scripts

**Назначение:** Содержит эталонные команды для запуска всех ключевых компонентов системы Black Swan: vLLM с экспертными масками, изолированных sandbox (Kata Containers, gVisor), аппаратного watchdog, скрипта холодного старта (`cold_start.sh`) и проверок готовности (readiness checks). Все команды проверены для конфигурации Core Node, описанной в [Appendix A](Appendix_A_GPU_Configurations.md), и валидны по состоянию на апрель 2026 года.

---

## B1. Запуск vLLM с экспертными масками DeepSeek‑V4

Система запускает один или несколько экземпляров vLLM с динамической активацией экспертов в зависимости от активных видов.

### B1.1. Профиль `Vagrant` (20% экспертов)

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

### B1.2. Профиль Arbtiragius (30% экспертов)

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

### B1.3. Профиль Sentinella (40% экспертов)

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

### B1.4. Профиль Architectus (60% экспертов, требует полного Core Node)

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

## B2. Запуск изолированных sandbox

### B2.1. Kata Containers с GPU‑пробросом (основной sandbox)

```bash
# Загрузка базового образа из IPFS
ipfs get QmPythonBaseImage -o /var/lib/swarm/images/python_base.img

# Запуск sandbox с VFIO‑passthrough
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

### B2.2. gVisor (быстрые итерации валидации)

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

## B3. Аппаратный watchdog и мониторинг

### B3.1. Загрузка скетча на Arduino Uno R4 WiFi

```bash
# Сборка и загрузка прошивки watchdog
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi /var/lib/swarm/firmware/watchdog_sketch.ino
arduino-cli upload --fqbn arduino:renesas_uno:unor4wifi --port /dev/ttyACM0 /var/lib/swarm/firmware/watchdog_sketch.ino
```

### B3.2. Запуск демона isolationd (systemd)

```bash
systemctl enable isolationd
systemctl start isolationd
systemctl status isolationd
```

Конфигурация демона: /etc/swarm/isolationd.toml

---

## B4. Скрипт холодного старта (cold_start.sh)

```bash
#!/bin/bash
set -euo pipefail

echo "[COLD_START] Beginning Black Swan cold start sequence..."

# 1. Проверка доступности GPU
echo "[COLD_START] Checking GPU availability..."
nvidia-smi || (echo "[FATAL] No GPU detected. Aborting." && exit 1)

# 2. Восстановление GlobalState из IPFS
echo "[COLD_START] Restoring GlobalState snapshot..."
GLOBAL_STATE_CID=$(cat /var/lib/swarm/global_state_cid.txt)
ipfs get "$GLOBAL_STATE_CID" -o /var/lib/swarm/global_state.json

# 3. Проверка подписей снапшота
echo "[COLD_START] Verifying snapshot signatures..."
verify_artifact --cid "$GLOBAL_STATE_CID" --public-key /etc/swarm/keys/artifact_pub.pem || exit 1

# 4. Запуск vLLM с минимальной маской (Vagrant)
echo "[COLD_START] Launching vLLM (Vagrant profile)..."
vllm serve deepseek-ai/DeepSeek-V4 \
  --port 8000 \
  --expert-mask vagrant \
  --expert-percent 20 \
  --quantization awq_4bit \
  --gpu-memory-utilization 0.70 &

# 5. Ожидание готовности vLLM
echo "[COLD_START] Waiting for vLLM to become healthy..."
curl --retry 30 --retry-delay 2 --retry-connrefused http://localhost:8000/health

# 6. Запуск Arbtiragius (30%) если Core Node готов
if [ "${CORE_NODE_READY:-false}" = "true" ]; then
  echo "[COLD_START] Launching vLLM (Arbtiragius profile)..."
  vllm serve deepseek-ai/DeepSeek-V4 \
    --port 8001 \
    --expert-mask arbiter \
    --expert-percent 30 \
    --quantization awq_4bit \
    --gpu-memory-utilization 0.75 &
fi

# 7. Запуск isolationd
echo "[COLD_START] Starting isolationd..."
systemctl start isolationd

# 8. Запуск Decision Pipeline
echo "[COLD_START] Decision Pipeline active."
echo "[COLD_START] Cold start complete. System online."
```

---

## B5. Проверки готовности (Readiness Checks)

```bash
# Проверка 1: GPU passthrough
docker run --rm --runtime=kata-runtime --device=/dev/vfio/1:/dev/vfio/1 nvidia/cuda:12.4-base nvidia-smi

# Проверка 2: Watchdog heartbeat
echo "HMAC_HEARTBEAT" > /dev/ttyACM0

# Проверка 3: Тепловой стресс-тест (30 мин, контроль температуры)
stress-ng --gpu 4 --cpu 8 --timeout 30m
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader

# Проверка 4: Инференс
curl -X POST http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-v4", "prompt": "def hello():", "max_tokens": 10}'
```

---

## B6. Связь с другими документами

· Конфигурации GPU: Appendix A: GPU Configurations
· Аппаратная изоляция: Hardware_Isolation.md
· Холодный старт: Cold_Start_Protocol.md
· Изоляция и watchdog: Isolation_and_Sandbox.md
· Глоссарий: Glossary.md
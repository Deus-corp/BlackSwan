# ================================
# STAGE 1: сборка зависимостей
# ================================
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ================================
# STAGE 2: финальный образ
# ================================
FROM python:3.11-slim AS final

WORKDIR /app

# Устанавливаем runtime-библиотеку, необходимую для llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем только установленные пакеты из builder'а
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем код проекта
COPY . /app

RUN chmod +x /app/mvp/lab_swarm_demo/node_entrypoint_async.sh

ENTRYPOINT ["/app/mvp/lab_swarm_demo/node_entrypoint_async.sh"]
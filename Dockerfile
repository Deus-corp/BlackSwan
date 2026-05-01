FROM python:3.11-slim

WORKDIR /app

# Устанавливаем компилятор для сборки llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN chmod +x /app/mvp/lab_swarm_demo/node_entrypoint_async.sh

ENTRYPOINT ["/app/mvp/lab_swarm_demo/node_entrypoint_async.sh"]
# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

FROM python:3.11-slim AS final
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . /app
RUN if [ -f /app/node_entrypoint_async.sh ]; then chmod +x /app/node_entrypoint_async.sh; fi
ENTRYPOINT ["/app/node_entrypoint_async.sh"]
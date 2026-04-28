FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
# файл node_entrypoint.sh уже должен быть исполняемым на хосте
ENTRYPOINT ["/app/mvp/lab_swarm_demo/node_entrypoint.sh"]
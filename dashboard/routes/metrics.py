import re
from collections import defaultdict
from fastapi import APIRouter
import docker
from prometheus_client import Gauge, generate_latest, CollectorRegistry
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()
registry = CollectorRegistry()

capital_gauge = Gauge('swarm_capital', 'Capital per node', ['node'], registry=registry)
fitness_gauge = Gauge('swarm_fitness', 'Fitness per node', ['node'], registry=registry)
diversity_gauge = Gauge('swarm_diversity', 'Diversity per node', ['node'], registry=registry)
crdt_size_gauge = Gauge('swarm_crdt_size', 'CRDT size per node', ['node'], registry=registry)

def update_prometheus_metrics(metrics_dict: dict):
    """Обновляет метрики из словаря, полученного от collect_metrics()."""
    for node, data in metrics_dict.items():
        capital_gauge.labels(node=node).set(data.get('capital', 0))
        fitness_gauge.labels(node=node).set(data.get('fitness', 0))
        diversity_gauge.labels(node=node).set(data.get('diversity', 0))
        crdt_size_gauge.labels(node=node).set(data.get('crdt_size', 0))

@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    from dashboard.routes.metrics import collect_metrics  # наша старая функция
    data = collect_metrics()
    update_prometheus_metrics(data)
    return generate_latest(registry)

client = docker.from_env()
LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)

def collect_metrics():
    metrics = defaultdict(dict)
    containers = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=200).decode('utf-8')
        except docker.errors.APIError:
            continue
        matches = LOG_PATTERN.findall(log)
        if matches:
            last = matches[-1]
            node = c.name.replace("lab_swarm_demo-", "")
            metrics[node] = {
                "step": int(last[1]),
                "capital": float(last[2]),
                "fitness": float(last[3]),
                "diversity": float(last[4]),
                "crdt_size": int(last[5]),
                "niche": last[6],
            }
    return metrics

@router.get("/api/metrics")
def api_metrics():
    return collect_metrics()
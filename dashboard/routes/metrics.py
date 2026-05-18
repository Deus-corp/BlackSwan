import re
from collections import defaultdict
from typing import Any
from fastapi import APIRouter
import docker
from prometheus_client import Gauge, generate_latest, CollectorRegistry
from fastapi.responses import PlainTextResponse

router = APIRouter()
registry = CollectorRegistry()

capital_gauge: Gauge = Gauge('swarm_capital', 'Capital per node', ['node'], registry=registry)
fitness_gauge: Gauge = Gauge('swarm_fitness', 'Fitness per node', ['node'], registry=registry)
diversity_gauge: Gauge = Gauge('swarm_diversity', 'Diversity per node', ['node'], registry=registry)
crdt_size_gauge: Gauge = Gauge('swarm_crdt_size', 'CRDT size per node', ['node'], registry=registry)

def update_prometheus_metrics(metrics_dict: dict[str, dict[str, float | int | str]]) -> None:
    """Обновляет метрики из словаря, полученного от collect_metrics()."""
    for node, data in metrics_dict.items():
        capital_gauge.labels(node=node).set(data.get('capital', 0))
        fitness_gauge.labels(node=node).set(data.get('fitness', 0))
        diversity_gauge.labels(node=node).set(data.get('diversity', 0))
        crdt_size_gauge.labels(node=node).set(data.get('crdt_size', 0))

@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> PlainTextResponse:
    """
    Exposes Prometheus metrics for the swarm nodes.
    Retrieves metrics from containers and updates the Prometheus gauges.
    """
    # collect_metrics is defined later in this file and will be available in the global scope
    # once the module is loaded. The import here is redundant and can cause issues.
    # from dashboard.routes.metrics import collect_metrics  # наша старая функция
    data = collect_metrics()
    update_prometheus_metrics(data)
    return PlainTextResponse(generate_latest(registry))

client: docker.client.DockerClient = docker.from_env()
LOG_PATTERN: re.Pattern[str] = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)

def collect_metrics() -> defaultdict[str, dict[str, Any]]:
    """
    Collects metrics from running Docker swarm nodes by parsing their logs.
    Returns a dictionary where keys are node names and values are dictionaries of their latest metrics.
    """
    metrics: defaultdict[str, dict[str, Any]] = defaultdict(dict)
    containers: list[docker.models.containers.Container] = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})
    for c in containers:
        try:
            log: str = c.logs(tail=200).decode('utf-8')
        except docker.errors.APIError:
            continue
        matches: list[tuple[str, ...]] = LOG_PATTERN.findall(log)
        if matches:
            last = matches[-1]
            node: str = c.name.replace("lab_swarm_demo-", "")
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
def api_metrics() -> defaultdict[str, dict[str, Any]]:
    """
    API endpoint to retrieve collected swarm node metrics in JSON format.
    """
    return collect_metrics()
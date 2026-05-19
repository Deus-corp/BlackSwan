"""
This module provides routes for collecting and exposing Prometheus metrics
related to Docker swarm nodes, as well as an API endpoint for fetching
these metrics in JSON format.
"""
import re
import logging
from collections import defaultdict
from typing import Any, Union

import docker
from fastapi import APIRouter
from prometheus_client import Gauge, generate_latest, CollectorRegistry
from fastapi.responses import PlainTextResponse

from dashboard.docker_service import list_containers, get_container_logs

logger = logging.getLogger(__name__)
router = APIRouter()
registry: CollectorRegistry = CollectorRegistry()

# Prometheus Gauges for swarm node metrics
capital_gauge: Gauge = Gauge('swarm_capital', 'Capital per node', ['node'], registry=registry)
fitness_gauge: Gauge = Gauge('swarm_fitness', 'Fitness per node', ['node'], registry=registry)
diversity_gauge: Gauge = Gauge('swarm_diversity', 'Diversity per node', ['node'], registry=registry)
crdt_size_gauge: Gauge = Gauge('swarm_crdt_size', 'CRDT size per node', ['node'], registry=registry)

def update_prometheus_metrics(metrics_dict: dict[str, dict[str, Union[float, int, str]]]) -> None:
    """
    Updates Prometheus gauges with metrics obtained from `collect_metrics()`.

    Args:
        metrics_dict (dict[str, dict[str, Union[float, int, str]]]): A dictionary
            where keys are node names and values are dictionaries of their latest metrics.
    """
    for node, data in metrics_dict.items():
        # Using .get() with a default of 0 to safely handle potentially missing metrics
        capital_gauge.labels(node=node).set(data.get('capital', 0))
        fitness_gauge.labels(node=node).set(data.get('fitness', 0))
        diversity_gauge.labels(node=node).set(data.get('diversity', 0))
        crdt_size_gauge.labels(node=node).set(data.get('crdt_size', 0))

@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    """
    Exposes Prometheus metrics for the swarm nodes.
    Retrieves metrics from containers and updates the Prometheus gauges.
    """
    data: dict[str, dict[str, Any]] = collect_metrics()
    update_prometheus_metrics(data)
    return PlainTextResponse(generate_latest(registry))

# Regex pattern to extract metrics from swarm node logs
LOG_PATTERN: re.Pattern[str] = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)

def collect_metrics() -> dict[str, dict[str, Any]]:
    """
    Collects metrics from running Docker swarm nodes by parsing their logs.
    It identifies containers by a specific name prefix and extracts the latest
    metrics (step, capital, fitness, diversity, crdt_size, niche) from their logs.

    Returns:
        dict[str, dict[str, Any]]: A dictionary where keys are node names and values
            are dictionaries of their latest metrics.
    """
    metrics: defaultdict[str, dict[str, Any]] = defaultdict(dict)
    containers: list[dict[str, Any]] = list_containers()
    for c in containers:
        container_name: str = c['name']
        try:
            log: str = get_container_logs(container_name, tail=200)
        except Exception:
            logger.exception(f"Error fetching logs for container: {container_name}")
            continue
        if not log:
            continue
        matches: list[tuple[str, ...]] = LOG_PATTERN.findall(log)
        if matches:
            last: tuple[str, ...] = matches[-1]
            node: str = container_name.replace("lab_swarm_demo-", "")
            metrics[node] = {
                "step": int(last[1]),
                "capital": float(last[2]),
                "fitness": float(last[3]),
                "diversity": float(last[4]),
                "crdt_size": int(last[5]),
                "niche": last[6],
            }
    return dict(metrics)

@router.get("/api/metrics")
async def api_metrics() -> dict[str, dict[str, Any]]:
    """
    API endpoint to retrieve collected swarm node metrics in JSON format.
    """
    return collect_metrics()
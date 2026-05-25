"""
This module provides routes for collecting and exposing Prometheus metrics
related to Docker swarm nodes, as well as an API endpoint for fetching
these metrics in JSON format.
"""

import logging
import re
from typing import Dict, List, TypedDict, Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from dashboard.docker_service import get_container_logs, list_containers

logger: logging.Logger = logging.getLogger(__name__)
router: APIRouter = APIRouter()
registry: CollectorRegistry = CollectorRegistry()


class SwarmMetrics(TypedDict):
    """Type definition for swarm node metrics."""
    step: int
    capital: float
    fitness: float
    diversity: float
    crdt_size: int
    niche: str


# Prometheus Gauges for swarm node metrics
METRICS: Dict[str, Gauge] = {
    "capital": Gauge("swarm_capital", "Capital per node", ["node"], registry=registry),
    "fitness": Gauge("swarm_fitness", "Fitness per node", ["node"], registry=registry),
    "diversity": Gauge("swarm_diversity", "Diversity per node", ["node"], registry=registry),
    "crdt_size": Gauge("swarm_crdt_size", "CRDT size per node", ["node"], registry=registry),
}

# Regex pattern to extract metrics from swarm node logs
LOG_PATTERN: re.Pattern = re.compile(
    r"SwarmNode:\[(?P<node_id>[^\]]+)\]\s+step=(?P<step>\d+)\s+"
    r"capital=(?P<capital>[\d.]+)\s+dq=[\d.]+\s+fitness=(?P<fitness>[\d.]+)\s+"
    r"diversity=(?P<diversity>[\d.]+)\s+crdt_size=(?P<crdt_size>\d+)\s+niche=(?P<niche>\w+)"
)


def collect_metrics() -> Dict[str, SwarmMetrics]:
    """
    Collects metrics from running Docker swarm nodes by parsing their logs.

    Returns:
        A dictionary mapping node names to their latest parsed SwarmMetrics object.
    """
    metrics: Dict[str, SwarmMetrics] = {}
    containers: List[Dict[str, Any]] = list_containers()

    for container in containers:
        container_name: str = container.get("name", "unknown")
        try:
            log_data: str = get_container_logs(container_name, tail=200)
            if not log_data:
                continue

            matches = list(LOG_PATTERN.finditer(log_data))
            if matches:
                last = matches[-1].groupdict()
                node: str = container_name.replace("lab_swarm_demo-", "")
                metrics[node] = {
                    "step": int(last["step"]),
                    "capital": float(last["capital"]),
                    "fitness": float(last["fitness"]),
                    "diversity": float(last["diversity"]),
                    "crdt_size": int(last["crdt_size"]),
                    "niche": last["niche"],
                }
        except (ValueError, TypeError, KeyError, Exception) as e:
            logger.error("Error parsing logs for container %s: %s", container_name, e)
            continue

    return metrics


def update_prometheus_metrics(metrics_dict: Dict[str, SwarmMetrics]) -> None:
    """
    Updates Prometheus gauges with metrics from the provided dictionary.

    Args:
        metrics_dict: The dictionary containing metrics per node.
    """
    for node, data in metrics_dict.items():
        for key, gauge in METRICS.items():
            val = data.get(key) # type: ignore
            if val is not None:
                gauge.labels(node=node).set(val)


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    """
    Exposes Prometheus metrics for the swarm nodes.
    """
    data = collect_metrics()
    update_prometheus_metrics(data)
    return PlainTextResponse(generate_latest(registry))


@router.get("/api/metrics")
async def api_metrics() -> Dict[str, SwarmMetrics]:
    """
    API endpoint to retrieve collected swarm node metrics in JSON format.
    """
    return collect_metrics()
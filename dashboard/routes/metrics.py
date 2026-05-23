"""
This module provides routes for collecting and exposing Prometheus metrics
related to Docker swarm nodes, as well as an API endpoint for fetching
these metrics in JSON format.
"""

import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, TypedDict

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from dashboard.docker_service import get_container_logs, list_containers

logger = logging.getLogger(__name__)
router = APIRouter()
registry = CollectorRegistry()


class SwarmMetrics(TypedDict):
    """Type definition for swarm node metrics."""
    step: int
    capital: float
    fitness: float
    diversity: float
    crdt_size: int
    niche: str


# Prometheus Gauges for swarm node metrics
METRICS = {
    "capital": Gauge("swarm_capital", "Capital per node", ["node"], registry=registry),
    "fitness": Gauge("swarm_fitness", "Fitness per node", ["node"], registry=registry),
    "diversity": Gauge("swarm_diversity", "Diversity per node", ["node"], registry=registry),
    "crdt_size": Gauge("swarm_crdt_size", "CRDT size per node", ["node"], registry=registry),
}

# Regex pattern to extract metrics from swarm node logs
LOG_PATTERN = re.compile(
    r"SwarmNode:\[(?P<node_id>[^\]]+)\]\s+step=(?P<step>\d+)\s+"
    r"capital=(?P<capital>[\d.]+)\s+dq=[\d.]+\s+fitness=(?P<fitness>[\d.]+)\s+"
    r"diversity=(?P<diversity>[\d.]+)\s+crdt_size=(?P<crdt_size>\d+)\s+niche=(?P<niche>\w+)"
)


def collect_metrics() -> Dict[str, SwarmMetrics]:
    """
    Collects metrics from running Docker swarm nodes by parsing their logs.

    Returns:
        Dict mapping node names to their latest parsed metrics.
    """
    metrics: Dict[str, SwarmMetrics] = {}
    containers = list_containers()

    for container in containers:
        container_name: str = container.get("name", "unknown")
        try:
            log_data = get_container_logs(container_name, tail=200)
            if not log_data:
                continue

            matches = list(LOG_PATTERN.finditer(log_data))
            if matches:
                last = matches[-1].groupdict()
                node = container_name.replace("lab_swarm_demo-", "")
                metrics[node] = {
                    "step": int(last["step"]),
                    "capital": float(last["capital"]),
                    "fitness": float(last["fitness"]),
                    "diversity": float(last["diversity"]),
                    "crdt_size": int(last["crdt_size"]),
                    "niche": last["niche"],
                }
        except Exception:
            logger.exception("Error fetching logs for container: %s", container_name)
            continue

    return metrics


def update_prometheus_metrics(metrics_dict: Dict[str, SwarmMetrics]) -> None:
    """
    Updates Prometheus gauges with metrics from the provided dictionary.
    """
    for node, data in metrics_dict.items():
        for key, gauge in METRICS.items():
            gauge.labels(node=node).set(data.get(key, 0))  # type: ignore


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
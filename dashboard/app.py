"""
BlackSwan Control Panel FastAPI application.

This module initializes the FastAPI application, mounts static files,
registers API routers, and sets up Prometheus metrics endpoints.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Union, TypedDict, Final

import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CollectorRegistry, Gauge, generate_latest

HOST: Final[str] = os.getenv("HOST", "0.0.0.0")
PORT: Final[int] = int(os.getenv("PORT", "8080"))
LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "info")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

app = FastAPI(title="BlackSwan Control Panel")

static_files_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_files_dir), name="static")

from dashboard.routes.control import router as control_router
from dashboard.routes.dashboard import router as dashboard_router
from dashboard.routes.logs import router as logs_router
from dashboard.routes.main import router as main_router
from dashboard.routes.metrics import collect_metrics, router as metrics_router
from dashboard.routes.mutations import router as mutations_router
from dashboard.routes.settings import router as settings_router
from dashboard.routes.trades import router as trades_router

app.include_router(main_router)
app.include_router(dashboard_router)
app.include_router(metrics_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(control_router)
app.include_router(trades_router)
app.include_router(mutations_router)

registry = CollectorRegistry()

capital_gauge = Gauge(
    'swarm_capital', 'Capital per node', ['node'], registry=registry
)
fitness_gauge = Gauge(
    'swarm_fitness', 'Fitness per node', ['node'], registry=registry
)
diversity_gauge = Gauge(
    'swarm_diversity', 'Diversity per node', ['node'], registry=registry
)
crdt_size_gauge = Gauge(
    'swarm_crdt_size', 'CRDT size per node', ['node'], registry=registry
)


class NodeMetrics(TypedDict):
    capital: Union[float, int]
    fitness: Union[float, int]
    diversity: Union[float, int]
    crdt_size: Union[float, int]


def _update_global_prometheus_gauges(
    metrics_dict: Dict[str, NodeMetrics]
) -> None:
    """
    Updates the global Prometheus gauges with provided metrics data.

    Iterates through the provided dictionary, setting the 'capital', 'fitness',
    'diversity', and 'crdt_size' gauges for each node. Missing keys default to 0.

    Args:
        metrics_dict: A dictionary where keys are node names (str) and values
                      are dictionaries (NodeMetrics) containing metric names (str)
                      and their corresponding values (float or int).

    Raises:
        ValueError: If any metric value is non-finite.
    """
    for node, data in metrics_dict.items():
        for key, value in data.items():
            if not np.isfinite(value):
                raise ValueError(f"Non-finite value encountered for node '{node}', metric '{key}': {value}")
        capital_gauge.labels(node=node).set(data.get('capital', 0))
        fitness_gauge.labels(node=node).set(data.get('fitness', 0))
        diversity_gauge.labels(node=node).set(data.get('diversity', 0))
        crdt_size_gauge.labels(node=node).set(data.get('crdt_size', 0))


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> PlainTextResponse:
    """
    Prometheus metrics endpoint.

    Collects current metrics from the system via `collect_metrics()`,
    updates the global Prometheus gauges defined in this file, and
    then returns the latest metrics in Prometheus text format.
    """
    data: Dict[str, NodeMetrics] = collect_metrics()
    _update_global_prometheus_gauges(data)
    return PlainTextResponse(generate_latest(registry).decode("utf-8"))


if __name__ == "__main__":
    print(f"🌐 Панель управления запущена на http://localhost:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL)
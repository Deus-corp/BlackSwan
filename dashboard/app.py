"""
BlackSwan Control Panel FastAPI application.

This module initializes the FastAPI application, mounts static files,
registers API routers, and sets up Prometheus metrics endpoints.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Final, TypedDict, Union

import numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CollectorRegistry, Gauge, generate_latest

# Configure path resolution for module discovery
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dashboard.routes.control import router as control_router
from dashboard.routes.dashboard import router as dashboard_router
from dashboard.routes.logs import router as logs_router
from dashboard.routes.main import router as main_router
from dashboard.routes.metrics import collect_metrics, router as metrics_router
from dashboard.routes.mutations import router as mutations_router
from dashboard.routes.settings import router as settings_router
from dashboard.routes.trades import router as trades_router

# Configuration
HOST: Final[str] = os.getenv("HOST", "0.0.0.0")
PORT: Final[int] = int(os.getenv("PORT", "8080"))
LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "info")

app: FastAPI = FastAPI(title="BlackSwan Control Panel")

# Mount static assets
STATIC_DIR: Final[str] = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Register routers
app.include_router(main_router)
app.include_router(dashboard_router)
app.include_router(metrics_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(control_router)
app.include_router(trades_router)
app.include_router(mutations_router)

# Prometheus Metrics Setup
_REGISTRY: Final[CollectorRegistry] = CollectorRegistry()

CAPITAL_GAUGE: Final[Gauge] = Gauge("swarm_capital", "Capital per node", ["node"], registry=_REGISTRY)
FITNESS_GAUGE: Final[Gauge] = Gauge("swarm_fitness", "Fitness per node", ["node"], registry=_REGISTRY)
DIVERSITY_GAUGE: Final[Gauge] = Gauge("swarm_diversity", "Diversity per node", ["node"], registry=_REGISTRY)
CRDT_SIZE_GAUGE: Final[Gauge] = Gauge("swarm_crdt_size", "CRDT size per node", ["node"], registry=_REGISTRY)

class NodeMetrics(TypedDict):
    """Typed definition for node telemetry data."""
    capital: Union[float, int]
    fitness: Union[float, int]
    diversity: Union[float, int]
    crdt_size: Union[float, int]

def _update_global_prometheus_gauges(metrics_dict: Dict[str, NodeMetrics]) -> None:
    """
    Updates global Prometheus gauges with current node metrics.

    Args:
        metrics_dict: Dictionary mapping node identifiers to their metrics.

    Raises:
        ValueError: If provided metrics contain non-finite numeric values.
    """
    for node, data in metrics_dict.items():
        for key, value in data.items():
            if not np.isfinite(float(value)):
                raise ValueError(f"Non-finite value in node '{node}', metric '{key}': {value}")
        
        CAPITAL_GAUGE.labels(node=node).set(data.get("capital", 0))
        FITNESS_GAUGE.labels(node=node).set(data.get("fitness", 0))
        DIVERSITY_GAUGE.labels(node=node).set(data.get("diversity", 0))
        CRDT_SIZE_GAUGE.labels(node=node).set(data.get("crdt_size", 0))

@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics() -> PlainTextResponse:
    """
    Exposes current swarm telemetry in Prometheus format.

    Returns:
        PlainTextResponse: The formatted metrics data.
    """
    data: Dict[str, NodeMetrics] = collect_metrics()
    _update_global_prometheus_gauges(data)
    return PlainTextResponse(generate_latest(_REGISTRY).decode("utf-8"))

if __name__ == "__main__":
    print(f"🌐 Control Panel started at http://localhost:{PORT}")
    uvicorn.run("app:app", host=HOST, port=PORT, log_level=LOG_LEVEL, reload=False)
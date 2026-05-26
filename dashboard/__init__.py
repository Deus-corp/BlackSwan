"""
Dashboard module for BlackSwan swarm control.

This module provides components for visualizing and interacting with simulation 
results, including web-based interfaces and interactive data displays.
"""

from __future__ import annotations

from . import (
    app,
    cli,
    docker_service,
)

__all__ = [
    "app",
    "cli",
    "docker_service",
    "__version__",
]

# Versioning for the dashboard component
__version__: str = "0.1.0"
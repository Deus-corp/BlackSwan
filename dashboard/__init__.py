"""
Dashboard module for BlackSwan swarm control.

This module provides components for visualizing and interacting with simulation 
results, including web-based interfaces and interactive data displays.
"""

from __future__ import annotations

__all__ = [
    "app",
    "cli",
    "docker_service",
]

# Expose sub-modules for easier package access
from dashboard import (
    app,
    cli,
    docker_service,
)

# Versioning for the dashboard component
__version__: str = "0.1.0"
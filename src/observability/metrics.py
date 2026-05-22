"""
Prometheus-compatible metrics collector for Docker Swarm nodes.
"""
import logging
import re
from collections import defaultdict
from typing import Dict, Any, Final, List, Optional

import docker
import docker.models.containers
import docker.errors

logger = logging.getLogger(__name__)

# Global Docker client
CLIENT: Final[docker.DockerClient] = docker.from_env()

# Regex pattern to extract metrics from log lines.
LOG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'SwarmNode:\[(?P<node_id>[^\]]+)\]\s+'
    r'step=(?P<step>\d+)\s+'
    r'capital=(?P<capital>[\d.]+)\s+'
    r'dq=[\d.]+\s+'
    r'fitness=(?P<fitness>[\d.]+)\s+'
    r'diversity=(?P<diversity>[\d.]+)\s+'
    r'crdt_size=(?P<crdt_size>\d+)\s+'
    r'niche=(?P<niche>\w+)'
)

NICHE_MAP: Final[Dict[str, int]] = {"exploration": 0, "capital": 1, "survival": 2}

def collect_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Collects the latest metrics from running Docker Swarm node containers.

    Returns:
        A dictionary mapping node names to their parsed metric values.
    """
    metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
    
    try:
        containers = CLIENT.containers.list(
            filters={"name": "lab_swarm_demo-node", "status": "running"}
        )
    except docker.errors.APIError as e:
        logger.error("Failed to list containers: %s", e)
        return {}

    for container in containers:
        try:
            log_output: bytes = container.logs(tail=100)
            log_str: str = log_output.decode('utf-8', errors='replace')
            
            matches = list(LOG_PATTERN.finditer(log_str))
            if not matches:
                continue

            last_match = matches[-1].groupdict()
            node_name: str = container.name.replace("lab_swarm_demo-", "")
            
            metrics[node_name] = {
                "step": int(last_match["step"]),
                "capital": float(last_match["capital"]),
                "fitness": float(last_match["fitness"]),
                "diversity": float(last_match["diversity"]),
                "crdt_size": int(last_match["crdt_size"]),
                "niche": last_match["niche"],
            }
        except (docker.errors.APIError, ValueError, KeyError) as e:
            logger.warning("Failed to process logs for %s: %s", container.name, e)
            
    return dict(metrics)

def prometheus_format(metrics: Dict[str, Dict[str, Any]]) -> str:
    """
    Converts metrics dictionary into Prometheus exposition text format.
    """
    lines: List[str] = [
        "# HELP blackswan_capital Current capital of the node.", "# TYPE blackswan_capital gauge",
        "# HELP blackswan_fitness Current fitness of the node.", "# TYPE blackswan_fitness gauge",
        "# HELP blackswan_diversity Current diversity of the node.", "# TYPE blackswan_diversity gauge",
        "# HELP blackswan_crdt_size Current CRDT size of the node.", "# TYPE blackswan_crdt_size gauge",
        "# HELP blackswan_step Current simulation step of the node.", "# TYPE blackswan_step gauge",
        "# HELP blackswan_niche Current niche (0=exp, 1=cap, 2=surv).", "# TYPE blackswan_niche gauge",
    ]

    for node, data in metrics.items():
        label = f'node="{node}"'
        lines.extend([
            f'blackswan_capital{{{label}}} {data.get("capital", 0.0)}',
            f'blackswan_fitness{{{label}}} {data.get("fitness", 0.0)}',
            f'blackswan_diversity{{{label}}} {data.get("diversity", 0.0)}',
            f'blackswan_crdt_size{{{label}}} {data.get("crdt_size", 0)}',
            f'blackswan_step{{{label}}} {data.get("step", 0)}',
            f'blackswan_niche{{{label}}} {NICHE_MAP.get(data.get("niche", ""), 0)}'
        ])
    
    return "\n".join(lines) + "\n"
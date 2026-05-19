# src/observability/metrics.py
"""
Minimal Prometheus-compatible metrics collector.
Gathers data from the logs of running Docker Swarm nodes.
"""
import re
import logging
from collections import defaultdict
from typing import Dict, Any, List, cast

import docker
import docker.models.containers
import docker.errors

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Initialize the Docker client globally.
# This assumes the script runs in an environment where the Docker daemon is accessible.
client: docker.DockerClient = docker.from_env()

# Regex pattern to extract metrics from log lines.
# It captures: node_id, step, capital, fitness, diversity, crdt_size, niche.
# Using named capture groups for improved readability when accessing match results.
LOG_PATTERN: re.Pattern[str] = re.compile(
    r'SwarmNode:\[(?P<node_id>[^\]]+)\]\s+'
    r'step=(?P<step>\d+)\s+'
    r'capital=(?P<capital>[\d.]+)\s+'
    r'dq=[\d.]+\s+' # 'dq' is present in logs but not explicitly collected as a metric
    r'fitness=(?P<fitness>[\d.]+)\s+'
    r'diversity=(?P<diversity>[\d.]+)\s+'
    r'crdt_size=(?P<crdt_size>\d+)\s+'
    r'niche=(?P<niche>\w+)'
)

def collect_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Collects the latest metrics from the logs of all running Docker Swarm nodes.

    It searches for containers with names starting with 'lab_swarm_demo-node',
    reads the last 100 lines of logs from each container, parses them using
    a regular expression, and extracts metrics from the last found matching line.

    Returns:
        Dict[str, Dict[str, Any]]: A dictionary where keys are node names
        (e.g., "node-1") and values are dictionaries of metrics for that node
        (e.g., 'step', 'capital', 'fitness', 'diversity', 'crdt_size', 'niche').
        Returns an empty dictionary if no metrics can be collected or Docker is unreachable.
    """
    metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
    
    try:
        # Filter for running containers with names matching 'lab_swarm_demo-node'.
        # Docker's `name` filter often supports glob-like patterns, matching prefixes.
        containers: List[docker.models.containers.Container] = client.containers.list(
            filters={"name": "lab_swarm_demo-node", "status": "running"}
        )
    except docker.errors.APIError as e:
        logger.error(f"Error connecting to Docker daemon or listing containers: {e}")
        return {} # Return empty metrics if Docker API is not reachable

    for c in containers:
        try:
            # Fetch last 100 log lines and decode them
            log_output: bytes = c.logs(tail=100)
            log: str = log_output.decode('utf-8')
        except (docker.errors.APIError, UnicodeDecodeError) as e:
            logger.warning(f"Could not fetch or decode logs for container {c.name}: {e}")
            continue

        # Find all matches of the log pattern using `finditer` for named groups
        matches: List[re.Match[str]] = list(LOG_PATTERN.finditer(log))
        
        if matches:
            # Process only the last matching log entry, which represents the latest state
            last_match = matches[-1]
            
            # Extract node name by removing the common prefix
            # The `replace` method always returns a string, `cast` is used for explicit type hinting.
            node_name: str = cast(str, c.name.replace("lab_swarm_demo-", ""))
            
            # Access captured groups by name for clarity and robustness
            metrics[node_name] = {
                "step": int(last_match.group("step")),
                "capital": float(last_match.group("capital")),
                "fitness": float(last_match.group("fitness")),
                "diversity": float(last_match.group("diversity")),
                "crdt_size": int(last_match.group("crdt_size")),
                "niche": last_match.group("niche"),
            }
            logger.debug(f"Metrics collected for node: {node_name}")
        else:
            logger.debug(f"No matching log entries found for container {c.name}")
            
    return metrics

def prometheus_format(metrics: Dict[str, Dict[str, Any]]) -> str:
    """
    Converts a dictionary of collected metrics into Prometheus exposition text format.

    Args:
        metrics (Dict[str, Dict[str, Any]]): A dictionary of metrics, typically obtained
        from `collect_metrics()`. The keys are node names and values are dictionaries
        of metric key-value pairs.

    Returns:
        str: A multi-line string in Prometheus format, containing metrics for all nodes,
        with appropriate HELP and TYPE declarations.
    """
    lines: List[str] = []

    # Prometheus metric descriptions and types for each metric
    lines.append("# HELP blackswan_capital Current capital of the node.")
    lines.append("# TYPE blackswan_capital gauge")
    lines.append("# HELP blackswan_fitness Current fitness of the node.")
    lines.append("# TYPE blackswan_fitness gauge")
    lines.append("# HELP blackswan_diversity Current diversity of the node.")
    lines.append("# TYPE blackswan_diversity gauge")
    lines.append("# HELP blackswan_crdt_size Current CRDT size of the node.")
    lines.append("# TYPE blackswan_crdt_size gauge")
    lines.append("# HELP blackswan_step Current simulation step of the node.")
    lines.append("# TYPE blackswan_step gauge")
    lines.append("# HELP blackswan_niche Current niche of the node (0=exploration, 1=capital, 2=survival).")
    lines.append("# TYPE blackswan_niche gauge")

    # Mapping string niche names to numerical values for Prometheus
    niche_map: Dict[str, int] = {"exploration": 0, "capital": 1, "survival": 2}

    for node, data in metrics.items():
        node_label: str = f'node="{node}"'
        
        # Add metrics for each node, using .get() with a default to handle potentially missing keys gracefully
        lines.append(f'blackswan_capital{{{node_label}}} {data.get("capital", 0.0)}')
        lines.append(f'blackswan_fitness{{{node_label}}} {data.get("fitness", 0.0)}')
        lines.append(f'blackswan_diversity{{{node_label}}} {data.get("diversity", 0.0)}')
        lines.append(f'blackswan_crdt_size{{{node_label}}} {data.get("crdt_size", 0)}')
        lines.append(f'blackswan_step{{{node_label}}} {data.get("step", 0)}')
        
        # Get niche value, defaulting to 0 if the niche string is unknown or missing
        niche_val: int = niche_map.get(data.get("niche", ""), 0)
        lines.append(f'blackswan_niche{{{node_label}}} {niche_val}')
    
    # Add a final newline character as per Prometheus exposition format spec
    return "\n".join(lines) + "\n"

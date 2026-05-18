"""
Service module for interacting with Docker and Docker Compose for the BlackSwan Swarm.

Provides functions to start, stop, rebuild, get logs, and manage configuration
for the Dockerized swarm environment.
"""

import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Union

import docker

# Define the project root and Docker Compose file path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_ROOT / "mvp" / "lab_swarm_demo" / "docker-compose.async.yml"


def run_command(cmd: str, cwd: Path = PROJECT_ROOT) -> str:
    """
    Executes a shell command from the specified current working directory
    and returns its stdout or stderr output.

    Args:
        cmd: The shell command string to execute.
        cwd: The current working directory from which to run the command.
             Defaults to PROJECT_ROOT.

    Returns:
        The combined standard output and standard error of the command.
    """
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, check=False
    )
    return result.stdout.strip() or result.stderr.strip()


def start_swarm(scale: int = 1) -> str:
    """
    Starts the Docker swarm services defined in COMPOSE_FILE, scaling the 'node'
    service to the specified number.

    Args:
        scale: The number of 'node' service instances to run. Defaults to 1.

    Returns:
        The output of the docker compose command.
    """
    absolute_compose_file = COMPOSE_FILE.resolve()
    return run_command(
        f"docker compose -f {absolute_compose_file} up -d --scale node={scale}"
    )


def stop_swarm() -> str:
    """
    Stops and removes the Docker swarm services defined in COMPOSE_FILE.

    Returns:
        The output of the docker compose command.
    """
    absolute_compose_file = COMPOSE_FILE.resolve()
    return run_command(f"docker compose -f {absolute_compose_file} down")


def rebuild_swarm(scale: int = 1) -> str:
    """
    Stops, rebuilds (with no cache), and then restarts the Docker swarm services.

    Args:
        scale: The number of 'node' service instances to run after rebuilding.
               Defaults to 1.

    Returns:
        The combined output of the stop, build, and start commands.
    """
    stop_output = stop_swarm()
    absolute_compose_file = COMPOSE_FILE.resolve()
    build_output = run_command(
        f"docker compose -f {absolute_compose_file} build --no-cache"
    )
    start_output = start_swarm(scale)
    return f"{stop_output}\n{build_output}\n{start_output}"


def get_logs(tail: int = 50) -> str:
    """
    Retrieves the last N lines of logs for all services defined in COMPOSE_FILE.

    Args:
        tail: The number of last lines to retrieve for each service. Defaults to 50.

    Returns:
        The concatenated log output for all services.
    """
    absolute_compose_file = COMPOSE_FILE.resolve()
    return run_command(
        f"docker compose -f {absolute_compose_file} logs --tail {tail}"
    )


def save_logs_to_disk() -> str:
    """
    Saves logs from individual swarm nodes and a combined log to a timestamped
    directory on disk.

    Returns:
        A message indicating where the logs were saved.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dest_dir = PROJECT_ROOT / "logs" / f"swarm_logs_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Save individual node logs
    # Assuming nodes are named lab_swarm_demo-node-1, -node-2, etc.
    # It attempts to log for nodes 1-4.
    for i in range(1, 5):
        container_name = f"lab_swarm_demo-node-{i}"
        log = run_command(f"docker logs {container_name} 2>&1")
        (dest_dir / f"node-{i}.log").write_text(log)

    # Save combined logs from docker compose
    absolute_compose_file = COMPOSE_FILE.resolve()
    combined_log = run_command(
        f"docker compose -f {absolute_compose_file} logs --no-color 2>&1"
    )
    (dest_dir / "all_nodes.log").write_text(combined_log)

    return f"Logs saved to {dest_dir}"


def update_config(new_values: Dict[str, str]) -> str:
    """
    Replaces or adds environment variables in the COMPOSE_FILE.
    It identifies lines starting with '- KEY=' or 'KEY=' and updates them.
    New keys (not found in the file) are appended to the end of the file
    with an assumed indentation of '      - KEY=VALUE'.

    Note: This function uses line-by-line string manipulation, which can be
    fragile with complex YAML structures. It aims to preserve the original
    logic of updating existing lines and appending new ones.

    Args:
        new_values: A dictionary of {environment_variable_name: new_value}
                    to be updated or added.

    Returns:
        A success message.
    """
    lines = COMPOSE_FILE.read_text().splitlines()
    updated_keys: set[str] = set()
    new_lines: List[str] = []

    for line in lines:
        replaced = False
        for key, value in new_values.items():
            # Check for existing environment variable lines, either "- KEY=" or "KEY="
            if line.strip().startswith(f"- {key}=") or line.strip().startswith(
                f"{key}="
            ):
                indent = line[: len(line) - len(line.lstrip())]
                # Reconstruct the line with the new value, preserving indentation
                new_lines.append(f"{indent}- {key}={value}")
                updated_keys.add(key)
                replaced = True
                break
        if not replaced:
            # If the line was not replaced by any new_values, append it as is.
            # The original code's `if not any(...)` was slightly redundant
            # if `replaced` is correctly tracking modifications to the current line.
            new_lines.append(line)

    # Append any keys from new_values that were not found and updated in the file.
    # This appends them to the end of the file, preserving original behavior.
    for key, value in new_values.items():
        if key not in updated_keys:
            # Assumed indentation for new environment variables
            new_lines.append(f"      - {key}={value}")

    COMPOSE_FILE.write_text("\n".join(new_lines) + "\n")
    return "Configuration updated successfully."


def get_current_config() -> Dict[str, str]:
    """
    Retrieves the current values of predefined environment variables from the
    COMPOSE_FILE. It searches for both 'KEY=VALUE' and '- KEY=VALUE' formats.

    Returns:
        A dictionary where keys are environment variable names and values are
        their current string values.
    """
    content = COMPOSE_FILE.read_text()
    config: Dict[str, str] = {}
    variables = [
        "LLM_MODEL",
        "BURN_RATE",
        "FAILURE_PROB",
        "TOTAL_NODES",
        "GOSSIP_SIGNING_ENABLED",
        "MEMORY_API_ENABLED",
        "MARKET_MODE",
        "PRICE_SCALE",
        "TRADING_SYMBOLS",
        "INTERNET_RESEARCHER_ENABLED",
        "TRADINGVIEW_WEBHOOK_ENABLED",
        "ORDERBOOK_ANALYSIS_ENABLED",
        "HEDGE_ENABLED",
        "HEDGE_RATIO",
    ]

    for var in variables:
        # Search for "VAR=VALUE" or "- VAR=VALUE" in the file content
        match = re.search(rf"(?:-?\s*{var})=(\S+)", content)
        if match:
            config[var] = match.group(1)
    return config


# Initialize Docker client once
_docker_client = docker.from_env()


def list_containers() -> List[Dict[str, str]]:
    """
    Lists Docker containers related to the swarm nodes.

    Returns:
        A list of dictionaries, each representing a swarm node container
        with its name, status, and image.
    """
    containers = _docker_client.containers.list(
        filters={"name": "lab_swarm_demo-node"}, all=True
    )
    result: List[Dict[str, str]] = []
    for c in containers:
        result.append(
            {
                "id": c.short_id,  # Added short ID for more info
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else "unknown",
            }
        )
    return result


def get_swarm_logs(tail: int = 100) -> str:
    """
    Retrieves logs specifically from swarm node containers,
    excluding Grafana and Prometheus logs.

    Args:
        tail: The number of last lines to retrieve for each service. Defaults to 100.

    Returns:
        The filtered log output for swarm nodes.
    """
    absolute_compose_file = COMPOSE_FILE.resolve()
    cmd = f"docker compose -f {absolute_compose_file} logs --tail {tail}"
    # Run the command from PROJECT_ROOT for consistency
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT, check=False
    )
    output = result.stdout.strip() or result.stderr.strip()
    # Filter out lines containing 'prometheus' or 'grafana'
    filtered_lines = [
        line
        for line in output.splitlines()
        if 'prometheus' not in line and 'grafana' not in line
    ]
    return '\n'.join(filtered_lines)


def get_container_statuses() -> List[Dict[str, str]]:
    """
    Retrieves the status of Docker containers identified as swarm nodes.

    Returns:
        A list of dictionaries, each containing 'name', 'status', and 'image'
        for a swarm node container.
    """
    containers = _docker_client.containers.list(
        filters={"name": "lab_swarm_demo-node"}, all=True
    )
    result: List[Dict[str, str]] = []
    for c in containers:
        result.append(
            {
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else "unknown",
            }
        )
    return result


def get_container_stats(container_name: str) -> str:
    """
    Returns CPU and memory usage statistics for a given Docker container.

    Args:
        container_name: The name of the Docker container.

    Returns:
        A formatted string with CPU and memory usage, or an error message.
    """
    try:
        c = _docker_client.containers.get(container_name)
        stats: Dict[str, Any] = c.stats(stream=False)

        cpu_delta = (
            stats['cpu_stats']['cpu_usage']['total_usage']
            - stats['precpu_stats']['cpu_usage']['total_usage']
        )
        system_delta = (
            stats['cpu_stats']['system_cpu_usage']
            - stats['precpu_stats']['system_cpu_usage']
        )
        # Avoid division by zero
        cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta else 0.0

        mem_usage_bytes = stats['memory_stats']['usage']
        mem_limit_bytes = stats['memory_stats']['limit']
        mem_usage_mb = mem_usage_bytes / (1024 * 1024)
        mem_limit_mb = mem_limit_bytes / (1024 * 1024) if mem_limit_bytes else 0

        return f"CPU: {cpu_percent:.2f}%, MEM: {mem_usage_mb:.1f}MB / {mem_limit_mb:.1f}MB"
    except docker.errors.NotFound:
        return f"Error: Container '{container_name}' not found."
    except Exception as e:
        return f"Error getting stats for {container_name}: {str(e)}"


def inspect_container(container_name: str) -> str:
    """
    Retrieves basic inspection information for a Docker container.

    Args:
        container_name: The name of the Docker container.

    Returns:
        A formatted string with container details, or an error message.
    """
    try:
        c = _docker_client.containers.get(container_name)
        info = {
            "ID": c.short_id,
            "Image": c.image.tags[0] if c.image.tags else "none",
            "Status": c.status,
            "Created": c.attrs['Created'],
            "Platform": c.attrs.get('Platform', 'unknown'),
        }
        return "\n".join(f"{k}: {v}" for k, v in info.items())
    except docker.errors.NotFound:
        return f"Error: Container '{container_name}' not found."
    except Exception as e:
        return f"Error inspecting {container_name}: {str(e)}"


def pause_container(container_name: str) -> str:
    """
    Pauses a running Docker container.

    Args:
        container_name: The name of the Docker container.

    Returns:
        A success message or an error message.
    """
    try:
        c = _docker_client.containers.get(container_name)
        c.pause()
        return f"Container '{container_name}' paused."
    except docker.errors.NotFound:
        return f"Error: Container '{container_name}' not found."
    except docker.errors.APIError as e:
        return f"Error pausing container '{container_name}': {e}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


def unpause_container(container_name: str) -> str:
    """
    Unpauses a paused Docker container.

    Args:
        container_name: The name of the Docker container.

    Returns:
        A success message or an error message.
    """
    try:
        c = _docker_client.containers.get(container_name)
        c.unpause()
        return f"Container '{container_name}' unpaused."
    except docker.errors.NotFound:
        return f"Error: Container '{container_name}' not found."
    except docker.errors.APIError as e:
        return f"Error unpausing container '{container_name}': {e}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
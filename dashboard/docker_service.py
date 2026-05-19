"""
Service module for interacting with Docker and Docker Compose for the BlackSwan Swarm.

Provides functions to start, stop, rebuild, get logs, and manage configuration
for the Dockerized swarm environment.
"""
import logging
import re
import subprocess
import time
import functools
from pathlib import Path
from typing import Any
# If Python 3.9+ is guaranteed, `dict` and `list` can be used directly as type hints.
# Assuming Python 3.9+ for modern type hinting.
import docker
from docker.client import DockerClient
from docker.models.containers import Container # Added for explicit type hinting of Docker containers

# Define the project root and Docker Compose file path
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
COMPOSE_FILE: Path = PROJECT_ROOT / "mvp" / "lab_swarm_demo" / "docker-compose.async.yml"

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def _get_docker_client() -> DockerClient:
    """
    Returns a singleton Docker client instance.

    The client is initialized once on the first call and then cached for subsequent uses.
    """
    return docker.from_env()


def run_command(cmd: str, cwd: Path = PROJECT_ROOT) -> str:
    """
    Executes a shell command from the specified current working directory.
    It captures stdout and stderr. If the command fails (non-zero exit code),
    or if stdout is empty but stderr has content with a zero exit code,
    appropriate messages are logged.

    Args:
        cmd: The shell command string to execute.
        cwd: The current working directory from which to run the command.
             Defaults to PROJECT_ROOT.

    Returns:
        The stripped standard output of the command. If stdout is empty
        but the command was successful (returncode == 0), the stripped
        standard error is returned. If the command failed (returncode != 0),
        it returns stdout or stderr (whichever is available), prioritizing
        stderr if stdout is empty, and logs an error with details.
    """
    logger.debug(f"Running command: '{cmd}' in '{cwd}'")
    result: subprocess.CompletedProcess[str] = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, check=False
    )
    stdout_stripped: str = result.stdout.strip()
    stderr_stripped: str = result.stderr.strip()

    if result.returncode != 0:
        logger.error(f"Command failed with exit code {result.returncode}: {cmd}")
        if stdout_stripped:
            logger.error(f"Stdout: {stdout_stripped}")
        if stderr_stripped:
            logger.error(f"Stderr: {stderr_stripped}")
        returned_output: str = stdout_stripped or stderr_stripped
        if returned_output:
            logger.error(f"Returning: '{returned_output}' as output from failed command.")
        else:
            logger.error("No output to return for failed command.")
        return returned_output
    elif not stdout_stripped and stderr_stripped:
        logger.warning(
            f"Command '{cmd}' produced no stdout, but had stderr: {stderr_stripped}. "
            f"Returning stderr as output."
        )
        return stderr_stripped
    return stdout_stripped


def start_swarm(scale: int = 1) -> str:
    """
    Starts the Docker swarm services defined in COMPOSE_FILE, scaling the 'node'
    service to the specified number.

    Args:
        scale: The number of 'node' service instances to run. Defaults to 1.

    Returns:
        The output of the docker compose command.
    """
    absolute_compose_file: Path = COMPOSE_FILE.resolve()
    return run_command(
        f"docker compose -f {absolute_compose_file} up -d --scale node={scale}"
    )


def stop_swarm() -> str:
    """
    Stops and removes the Docker swarm services defined in COMPOSE_FILE.

    Returns:
        The output of the docker compose command.
    """
    absolute_compose_file: Path = COMPOSE_FILE.resolve()
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
    stop_output: str = stop_swarm()
    absolute_compose_file: Path = COMPOSE_FILE.resolve()
    build_output: str = run_command(
        f"docker compose -f {absolute_compose_file} build --no-cache"
    )
    start_output: str = start_swarm(scale)
    return f"{stop_output}\n{build_output}\n{start_output}"


def get_logs(tail: int = 50) -> str:
    """
    Retrieves the last N lines of logs for all services defined in COMPOSE_FILE.

    Args:
        tail: The number of last lines to retrieve for each service. Defaults to 50.

    Returns:
        The concatenated log output for all services.
    """
    absolute_compose_file: Path = COMPOSE_FILE.resolve()
    return run_command(
        f"docker compose -f {absolute_compose_file} logs --tail {tail}"
    )


def save_logs_to_disk() -> str:
    """
    Saves logs from individual swarm nodes and a combined log to a timestamped
    directory on disk.

    Note: This function currently attempts to retrieve logs for nodes named
    'lab_swarm_demo-node-1' through '-4'. If the swarm contains a different
    number or naming convention for nodes, this range may need adjustment.

    Returns:
        A message indicating where the logs were saved.
    """
    timestamp: str = time.strftime("%Y%m%d_%H%M%S")
    dest_dir: Path = PROJECT_ROOT / "logs" / f"swarm_logs_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Save individual node logs
    for i in range(1, 5):  # Attempts to log for nodes 1-4.
        container_name: str = f"lab_swarm_demo-node-{i}"
        log_output: str = run_command(f"docker logs {container_name} 2>&1")
        (dest_dir / f"node-{i}.log").write_text(log_output)

    # Save combined logs from docker compose
    absolute_compose_file: Path = COMPOSE_FILE.resolve()
    combined_log_output: str = run_command(
        f"docker compose -f {absolute_compose_file} logs --no-color 2>&1"
    )
    (dest_dir / "all_nodes.log").write_text(combined_log_output)

    return f"Logs saved to {dest_dir}"


def update_config(new_values: dict[str, str]) -> str:
    """
    Replaces or adds environment variables in the COMPOSE_FILE.
    It identifies lines starting with '- KEY=' or 'KEY=' and updates them.
    New keys (not found in the file) are appended to the end of the file
    with an assumed indentation of '      - KEY=VALUE'.

    Note: This function uses line-by-line string manipulation, which is
    fragile with complex YAML structures. It aims to preserve the original
    logic of updating existing lines and appending new ones.
    A significant behavior is that any existing environment variable line
    identified (e.g., `  KEY=VALUE`) will be rewritten with a leading dash
    and indentation (e.g., `    - KEY=VALUE`), effectively converting a
    dictionary style entry to a list style entry in the YAML if it wasn't
    already. The indentation for new keys is hardcoded to 6 spaces.

    Args:
        new_values: A dictionary of {environment_variable_name: new_value}
                    to be updated or added.

    Returns:
        A success message.
    """
    lines: list[str] = COMPOSE_FILE.read_text().splitlines()
    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        replaced: bool = False
        for key, value in new_values.items():
            # Check for existing environment variable lines, either "- KEY=" or "KEY="
            if line.strip().startswith(f"- {key}=") or line.strip().startswith(
                f"{key}="
            ):
                indent: str = line[: len(line) - len(line.lstrip())]
                # Reconstruct the line with the new value, preserving indentation
                # and ensuring it's in '- KEY=VALUE' format.
                new_lines.append(f"{indent}- {key}={value}")
                updated_keys.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    # Append any keys from new_values that were not found and updated in the file.
    # This appends them to the end of the file, preserving original behavior.
    for key, value in new_values.items():
        if key not in updated_keys:
            # Assumed indentation for new environment variables
            new_lines.append(f"      - {key}={value}")

    COMPOSE_FILE.write_text("\n".join(new_lines) + "\n")
    return "Configuration updated successfully."


def get_current_config() -> dict[str, str]:
    """
    Retrieves the current values of predefined environment variables from the
    COMPOSE_FILE. It searches for both 'KEY=VALUE' and '- KEY=VALUE' formats.

    Returns:
        A dictionary where keys are environment variable names and values are
        their current string values.
    """
    content: str = COMPOSE_FILE.read_text()
    config: dict[str, str] = {}
    variables: list[str] = [
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


def list_containers() -> list[dict[str, str]]:
    """
    Lists Docker containers related to the swarm nodes.

    Returns:
        A list of dictionaries, each containing 'id', 'name', 'status', and 'image'
        for a swarm node container.
    """
    client: DockerClient = _get_docker_client()
    containers: list[Container] = client.containers.list(
        filters={"name": "lab_swarm_demo-node"}, all=True
    )
    result: list[dict[str, str]] = []
    for c in containers:
        result.append(
            {
                "id": c.short_id,
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
    absolute_compose_file: Path = COMPOSE_FILE.resolve()
    cmd: str = f"docker compose -f {absolute_compose_file} logs --tail {tail}"
    # Run the command from PROJECT_ROOT for consistency
    result: subprocess.CompletedProcess[str] = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT, check=False
    )
    output: str = result.stdout.strip() or result.stderr.strip()
    # Filter out lines containing 'prometheus' or 'grafana'
    filtered_lines: list[str] = [
        line
        for line in output.splitlines()
        if 'prometheus' not in line and 'grafana' not in line
    ]
    return '\n'.join(filtered_lines)


def get_container_statuses() -> list[dict[str, str]]:
    """
    Retrieves the status of Docker containers identified as swarm nodes.

    Returns:
        A list of dictionaries, each containing 'name', 'status', and 'image'
        for a swarm node container.
    """
    client: DockerClient = _get_docker_client()
    containers: list[Container] = client.containers.list(
        filters={"name": "lab_swarm_demo-node"}, all=True
    )
    result: list[dict[str, str]] = []
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
    client: DockerClient = _get_docker_client()
    try:
        c: Container = client.containers.get(container_name)
        stats: dict[str, Any] = c.stats(stream=False)

        cpu_delta: float = (
            stats['cpu_stats']['cpu_usage']['total_usage']
            - stats['precpu_stats']['cpu_usage']['total_usage']
        )
        system_delta: float = (
            stats['cpu_stats']['system_cpu_usage']
            - stats['precpu_stats']['system_cpu_usage']
        )
        # Avoid division by zero
        cpu_percent: float = (cpu_delta / system_delta) * 100.0 if system_delta else 0.0

        mem_usage_bytes: int = stats['memory_stats']['usage']
        mem_limit_bytes: int = stats['memory_stats']['limit']
        mem_usage_mb: float = mem_usage_bytes / (1024 * 1024)
        mem_limit_mb: float = mem_limit_bytes / (1024 * 1024) if mem_limit_bytes else 0.0

        return f"CPU: {cpu_percent:.2f}%, MEM: {mem_usage_mb:.1f}MB / {mem_limit_mb:.1f}MB"
    except docker.errors.NotFound:
        logger.error(f"Container '{container_name}' not found for stats.")
        return f"Error: Container '{container_name}' not found."
    except Exception as e:
        logger.exception(f"Error getting stats for {container_name}")
        return f"Error getting stats for {container_name}: {str(e)}"


def inspect_container(container_name: str) -> str:
    """
    Retrieves basic inspection information for a Docker container.

    Args:
        container_name: The name of the Docker container.

    Returns:
        A formatted string with container details, or an error message.
    """
    client: DockerClient = _get_docker_client()
    try:
        c: Container = client.containers.get(container_name)
        info: dict[str, str] = {
            "ID": c.short_id,
            "Image": c.image.tags[0] if c.image.tags else "none",
            "Status": c.status,
            "Created": c.attrs['Created'],
            "Platform": c.attrs.get('Platform', 'unknown'),
        }
        return "\n".join(f"{k}: {v}" for k, v in info.items())
    except docker.errors.NotFound:
        logger.error(f"Container '{container_name}' not found for inspection.")
        return f"Error: Container '{container_name}' not found."
    except Exception as e:
        logger.exception(f"Error inspecting {container_name}")
        return f"Error inspecting {container_name}: {str(e)}"


def pause_container(container_name: str) -> str:
    """
    Pauses a running Docker container.

    Args:
        container_name: The name of the Docker container.

    Returns:
        A success message or an error message.
    """
    client: DockerClient = _get_docker_client()
    try:
        c: Container = client.containers.get(container_name)
        c.pause()
        return f"Container '{container_name}' paused."
    except docker.errors.NotFound:
        logger.error(f"Container '{container_name}' not found for pausing.")
        return f"Error: Container '{container_name}' not found."
    except docker.errors.APIError as e:
        logger.error(f"API Error pausing container '{container_name}': {e}")
        return f"Error pausing container '{container_name}': {e}"
    except Exception as e:
        logger.exception(f"An unexpected error occurred while pausing '{container_name}'")
        return f"An unexpected error occurred: {str(e)}"


def unpause_container(container_name: str) -> str:
    """
    Unpauses a paused Docker container.

    Args:
        container_name: The name of the Docker container.

    Returns:
        A success message or an error message.
    """
    client: DockerClient = _get_docker_client()
    try:
        c: Container = client.containers.get(container_name)
        c.unpause()
        return f"Container '{container_name}' unpaused."
    except docker.errors.NotFound:
        logger.error(f"Container '{container_name}' not found for unpausing.")
        return f"Error: Container '{container_name}' not found."
    except docker.errors.APIError as e:
        logger.error(f"API Error unpausing container '{container_name}': {e}")
        return f"Error unpausing container '{container_name}': {e}"
    except Exception as e:
        logger.exception(f"An unexpected error occurred while unpausing '{container_name}'")
        return f"An unexpected error occurred: {str(e)}"


def get_container_logs(container_name: str, tail: int = 200) -> str:
    """
    Retrieves the last N lines of logs for a specific Docker container.

    Args:
        container_name: The name of the Docker container.
        tail: The number of last lines to retrieve. Defaults to 200.

    Returns:
        The log output of the container, or an empty string if an error occurs.
    """
    client: DockerClient = _get_docker_client()
    try:
        c: Container = client.containers.get(container_name)
        # decode('utf-8', errors='ignore') to handle potential non-UTF8 characters in logs
        return c.logs(tail=tail).decode('utf-8', errors='ignore')
    except docker.errors.NotFound:
        logger.error(f"Container '{container_name}' not found for logs.")
        return ""
    except Exception as e:
        logger.exception(f"Error getting logs for {container_name}")
        return ""
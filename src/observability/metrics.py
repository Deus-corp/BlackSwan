# src/observability/metrics.py
"""
Минимальный Prometheus-совместимый коллектор метрик.
Собирает данные из логов работающих узлов Docker Swarm.
"""
import re
from collections import defaultdict
from typing import Dict, Any

import docker
import docker.models.containers
import docker.errors

# Initialize the Docker client globally.
# This assumes the script runs in an environment where Docker daemon is accessible.
client: docker.client.DockerClient = docker.from_env()

# Regex pattern to extract metrics from log lines.
# It captures: node_id, step, capital, fitness, diversity, crdt_size, niche.
LOG_PATTERN: re.Pattern[str] = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)

def collect_metrics() -> Dict[str, Dict[str, Any]]:
    """
    Собирает последние метрики из логов всех запущенных узлов Docker Swarm.

    Ищет контейнеры с именем, начинающимся на 'lab_swarm_demo-node',
    считывает последние 100 строк логов каждого контейнера,
    парсит их с помощью регулярного выражения и извлекает метрики
    из последней найденной строки.

    Returns:
        Dict[str, Dict[str, Any]]: Словарь, где ключом является имя узла
        (без префикса "lab_swarm_demo-"), а значением - словарь метрик
        для этого узла (step, capital, fitness, diversity, crdt_size, niche).
    """
    metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
    # Filter for running containers named 'lab_swarm_demo-node'
    containers: list[docker.models.containers.Container] = client.containers.list(
        filters={"name": "lab_swarm_demo-node", "status": "running"}
    )

    for c in containers:
        try:
            # Fetch last 100 log lines and decode them
            log: str = c.logs(tail=100).decode('utf-8')
        except (docker.errors.APIError, UnicodeDecodeError) as e:
            # Skip container if logs cannot be fetched or decoded
            print(f"Warning: Could not fetch or decode logs for container {c.name}: {e}")
            continue

        # Find all matches of the log pattern
        matches: list[tuple[str, ...]] = LOG_PATTERN.findall(log)
        if matches:
            # Process only the last matching log entry
            last_match = matches[-1]
            # Extract node name by removing the common prefix
            node_name: str = c.name.replace("lab_swarm_demo-", "")
            metrics[node_name] = {
                "step": int(last_match[1]),
                "capital": float(last_match[2]),
                "fitness": float(last_match[3]),
                "diversity": float(last_match[4]),
                "crdt_size": int(last_match[5]),
                "niche": last_match[6],
            }
    return metrics

def prometheus_format(metrics: Dict[str, Dict[str, Any]]) -> str:
    """
    Преобразует словарь метрик в текстовый формат Prometheus.

    Args:
        metrics (Dict[str, Dict[str, Any]]): Словарь метрик, полученный
        из collect_metrics().

    Returns:
        str: Строка в формате Prometheus, содержащая метрики для всех узлов.
    """
    lines: list[str] = []

    # Prometheus metric descriptions
    lines.append("# HELP blackswan_capital Текущий капитал узла.")
    lines.append("# TYPE blackswan_capital gauge")
    lines.append("# HELP blackswan_fitness Текущая приспособленность узла.")
    lines.append("# TYPE blackswan_fitness gauge")
    lines.append("# HELP blackswan_diversity Текущее разнообразие узла.")
    lines.append("# TYPE blackswan_diversity gauge")
    lines.append("# HELP blackswan_crdt_size Текущий размер CRDT узла.")
    lines.append("# TYPE blackswan_crdt_size gauge")
    lines.append("# HELP blackswan_step Текущий шаг симуляции узла.")
    lines.append("# TYPE blackswan_step gauge")
    lines.append("# HELP blackswan_niche Текущая ниша узла (0=exploration, 1=capital, 2=survival).")
    lines.append("# TYPE blackswan_niche gauge")

    # Mapping string niche names to numerical values for Prometheus
    niche_map: Dict[str, int] = {"exploration": 0, "capital": 1, "survival": 2}

    for node, data in metrics.items():
        node_label: str = f'node="{node}"'
        lines.append(f'blackswan_capital{{{node_label}}} {data["capital"]}')
        lines.append(f'blackswan_fitness{{{node_label}}} {data["fitness"]}')
        lines.append(f'blackswan_diversity{{{node_label}}} {data["diversity"]}')
        lines.append(f'blackswan_crdt_size{{{node_label}}} {data["crdt_size"]}')
        lines.append(f'blackswan_step{{{node_label}}} {data["step"]}')
        
        # Get niche value, defaulting to 0 if unknown
        niche_val: int = niche_map.get(data["niche"], 0)
        lines.append(f'blackswan_niche{{{node_label}}} {niche_val}')
    
    # Add a final newline character as per Prometheus exposition format
    return "\n".join(lines) + "\n"
# src/observability/metrics.py
"""
Минимальный Prometheus-совместимый коллектор метрик.
Собирает данные из логов работающих узлов.
"""
import re
import docker
from collections import defaultdict

client = docker.from_env()

LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)

def collect_metrics() -> dict:
    """Собирает метрики из логов всех узлов и возвращает словарь."""
    metrics = defaultdict(dict)
    containers = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=100).decode('utf-8')
        except docker.errors.APIError:
            continue
        matches = LOG_PATTERN.findall(log)
        if matches:
            last = matches[-1]
            node = c.name.replace("lab_swarm_demo-", "")
            metrics[node] = {
                "step": int(last[1]),
                "capital": float(last[2]),
                "fitness": float(last[3]),
                "diversity": float(last[4]),
                "crdt_size": int(last[5]),
                "niche": last[6],
            }
    return metrics

def prometheus_format(metrics: dict) -> str:
    """Преобразует словарь метрик в текстовый формат Prometheus."""
    lines = []
    for node, data in metrics.items():
        node_label = f'node="{node}"'
        lines.append(f'blackswan_capital{{{node_label}}} {data["capital"]}')
        lines.append(f'blackswan_fitness{{{node_label}}} {data["fitness"]}')
        lines.append(f'blackswan_diversity{{{node_label}}} {data["diversity"]}')
        lines.append(f'blackswan_crdt_size{{{node_label}}} {data["crdt_size"]}')
        lines.append(f'blackswan_step{{{node_label}}} {data["step"]}')
        # niche как gauge: 0=exploration, 1=capital, 2=survival
        niche_map = {"exploration": 0, "capital": 1, "survival": 2}
        niche_val = niche_map.get(data["niche"], 0)
        lines.append(f'blackswan_niche{{{node_label}}} {niche_val}')
    return "\n".join(lines) + "\n"
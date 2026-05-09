import re
from collections import defaultdict
from fastapi import APIRouter
import docker

router = APIRouter()

client = docker.from_env()
LOG_PATTERN = re.compile(
    r'SwarmNode:\[([^\]]+)\]\s+step=(\d+)\s+capital=([\d.]+)\s+dq=[\d.]+\s+fitness=([\d.]+)\s+diversity=([\d.]+)\s+crdt_size=(\d+)\s+niche=(\w+)'
)

def collect_metrics():
    metrics = defaultdict(dict)
    containers = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=200).decode('utf-8')
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

@router.get("/api/metrics")
def api_metrics():
    return collect_metrics()
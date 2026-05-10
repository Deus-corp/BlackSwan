import subprocess
import re
import subprocess
import docker
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = PROJECT_ROOT / "mvp" / "lab_swarm_demo" / "docker-compose.async.yml"

def run_command(cmd: str) -> str:
    """Выполняет shell‑команду из корня проекта и возвращает stdout/stderr."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return result.stdout or result.stderr

def start_swarm(scale: int = 1) -> str:
    return run_command(f"docker compose -f {COMPOSE_FILE} up -d --scale node={scale}")

def stop_swarm():
    return run_command(f"docker compose -f {COMPOSE_FILE} down")

def rebuild_swarm():
    stop = stop_swarm()
    build = run_command(f"docker compose -f {COMPOSE_FILE} build --no-cache")
    start = start_swarm()
    return f"STOP:\n{stop}\nBUILD:\n{build}\nSTART:\n{start}"

def get_logs(tail: int = 50):
    return run_command(f"docker compose -f {COMPOSE_FILE} logs --tail {tail}")

def save_logs_to_disk():
    import time
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dest_dir = PROJECT_ROOT / "logs" / f"swarm_logs_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 5):
        log = run_command(f"docker logs lab_swarm_demo-node-{i} 2>&1")
        (dest_dir / f"node-{i}.log").write_text(log)
    combined = run_command(f"docker compose -f {COMPOSE_FILE} logs --no-color 2>&1")
    (dest_dir / "all_nodes.log").write_text(combined)
    return f"Logs saved to {dest_dir}"

def update_config(new_values: dict) -> str:
    """Заменяет значения переменных в COMPOSE_FILE на новые и перезапускает рой."""
    content = COMPOSE_FILE.read_text()
    for key, value in new_values.items():
        # ищем строку, начинающуюся с "key=" (учитывая возможные пробелы)
        content = content.replace(f"{key}=", f"{key}={value}")
    COMPOSE_FILE.write_text(content)
    stop_swarm()
    start_swarm()
    return "Configuration updated and swarm restarted."

def get_current_config() -> dict:
    content = COMPOSE_FILE.read_text()
    config = {}
    for var in ["LLM_MODEL", "BURN_RATE", "FAILURE_PROB", "TOTAL_NODES", "GOSSIP_SIGNING_ENABLED",
                "MEMORY_API_ENABLED", "MARKET_MODE", "PRICE_SCALE", "TRADING_SYMBOLS",
                "INTERNET_RESEARCHER_ENABLED", "TRADINGVIEW_WEBHOOK_ENABLED", "ORDERBOOK_ANALYSIS_ENABLED",
                "HEDGE_ENABLED", "HEDGE_RATIO"]:
        match = re.search(rf"{var}=(\S+)", content)
        if match:
            config[var] = match.group(1)
    return config

def list_containers():
    import docker
    client = docker.from_env()
    return client.containers.list(filters={"name": "lab_swarm_demo-node"})

def get_swarm_logs(tail: int = 100) -> str:
    """Возвращает логи только узлов роя, исключая grafana и prometheus."""
    cmd = f"docker compose -f {COMPOSE_FILE} logs --tail {tail}"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=COMPOSE_FILE.parent)
    output = result.stdout or result.stderr
    # Фильтруем строки, исключая grafana и prometheus
    filtered = []
    for line in output.splitlines():
        if 'prometheus' not in line and 'grafana' not in line:
            filtered.append(line)
    return '\n'.join(filtered)

def get_container_statuses():
    import docker
    client = docker.from_env()
    containers = client.containers.list(filters={"name": "lab_swarm_demo-node"}, all=True)
    result = []
    for c in containers:
        result.append({
            "name": c.name,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else "unknown",
        })
    return result

def get_container_stats(container_name: str):
    """Возвращает статистику использования CPU/памяти контейнера."""
    client = docker.from_env()
    try:
        c = client.containers.get(container_name)
        stats = c.stats(stream=False)
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        cpu_percent = (cpu_delta / system_delta) * 100.0
        mem_usage = stats['memory_stats']['usage'] / 1024 / 1024
        mem_limit = stats['memory_stats']['limit'] / 1024 / 1024
        return f"CPU: {cpu_percent:.2f}%, MEM: {mem_usage:.1f}MB / {mem_limit:.1f}MB"
    except Exception as e:
        return f"Error: {str(e)}"

def inspect_container(container_name: str):
    client = docker.from_env()
    try:
        c = client.containers.get(container_name)
        info = {
            "ID": c.short_id,
            "Image": c.image.tags[0] if c.image.tags else "none",
            "Status": c.status,
            "Created": c.attrs['Created'],
            "Platform": c.attrs.get('Platform', 'unknown'),
        }
        return "\n".join(f"{k}: {v}" for k, v in info.items())
    except Exception as e:
        return f"Error: {str(e)}"

def pause_container(container_name: str):
    client = docker.from_env()
    try:
        c = client.containers.get(container_name)
        c.pause()
        return f"Container {container_name} paused."
    except Exception as e:
        return f"Error: {str(e)}"

def unpause_container(container_name: str):
    client = docker.from_env()
    try:
        c = client.containers.get(container_name)
        c.unpause()
        return f"Container {container_name} unpaused."
    except Exception as e:
        return f"Error: {str(e)}"
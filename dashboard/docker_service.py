import subprocess
import re
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
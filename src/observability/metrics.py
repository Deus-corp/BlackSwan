"""Prometheus-compatible metrics collector for BlackSwan runtime nodes."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Final, Optional

logger = logging.getLogger(__name__)

try:
    import docker
    import docker.errors
except ImportError:
    docker = None  # type: ignore[assignment]


LOG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"SwarmNode:\[(?P<node_id>[^\]]+)\]\s+"
    r"step=(?P<step>\d+)\s+"
    r"capital=(?P<capital>[-+]?\d+(?:\.\d+)?)\s+"
    r"dq=(?P<dq>[-+]?\d+(?:\.\d+)?)\s+"
    r"fitness=(?P<fitness>[-+]?\d+(?:\.\d+)?)\s+"
    r"diversity=(?P<diversity>[-+]?\d+(?:\.\d+)?)\s+"
    r"crdt_size=(?P<crdt_size>\d+)\s+"
    r"niche=(?P<niche>[\w.-]+)"
)

TRADE_HEARTBEAT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"Publishing trade heartbeat payload: .*?"
    r"capital=(?P<capital>[-+]?\d+(?:\.\d+)?)\s+"
    r"dry_run=(?P<dry_run>True|False|true|false|1|0)\s+"
    r"execution_enabled=(?P<execution_enabled>True|False|true|false|1|0)"
)

NICHE_MAP: Final[dict[str, int]] = {
    "exploration": 0,
    "capital": 1,
    "survival": 2,
}

METRIC_DEFINITIONS: Final[tuple[tuple[str, str, str], ...]] = (
    ("blackswan_capital", "Current capital of the node.", "gauge"),
    ("blackswan_fitness", "Current fitness of the node.", "gauge"),
    ("blackswan_diversity", "Current diversity of the node.", "gauge"),
    ("blackswan_crdt_size", "Current CRDT size of the node.", "gauge"),
    ("blackswan_step", "Current simulation/runtime step of the node.", "gauge"),
    ("blackswan_dq", "Current survival drawdown/quality score of the node.", "gauge"),
    ("blackswan_niche", "Current niche code: 0=exploration, 1=capital, 2=survival.", "gauge"),
    ("blackswan_dry_run", "Whether trade node is in dry-run mode.", "gauge"),
    ("blackswan_execution_enabled", "Whether live execution is enabled.", "gauge"),
)


def collect_metrics(
    *,
    logs_dir: str | Path | None = None,
    crdt_db_path: str | Path | None = None,
    docker_name_filter: str = "lab_swarm_demo-node",
) -> dict[str, dict[str, Any]]:
    """Collect metrics from local runtime logs/CRDT and Docker when available."""
    metrics: dict[str, dict[str, Any]] = {}

    logs_metrics = collect_log_metrics(logs_dir=logs_dir)
    metrics.update(logs_metrics)

    crdt_metrics = collect_crdt_metrics(crdt_db_path=crdt_db_path)
    for node, data in crdt_metrics.items():
        metrics.setdefault(node, {}).update(data)

    docker_metrics = collect_docker_metrics(name_filter=docker_name_filter)
    for node, data in docker_metrics.items():
        metrics.setdefault(node, {}).update(data)

    return metrics


def collect_docker_metrics(name_filter: str = "lab_swarm_demo-node") -> dict[str, dict[str, Any]]:
    """Collect latest node metrics from Docker container logs if Docker is available."""
    if docker is None:
        return {}

    try:
        client = docker.from_env()
        containers = client.containers.list(filters={"name": name_filter, "status": "running"})
    except Exception as exc:
        logger.debug("Docker metrics unavailable: %s", exc)
        return {}

    metrics: dict[str, dict[str, Any]] = {}

    for container in containers:
        try:
            raw_logs = container.logs(tail=200)
            log_text = raw_logs.decode("utf-8", errors="replace")
            parsed = _parse_latest_log_metrics(log_text)
            if not parsed:
                continue

            node_name = str(getattr(container, "name", "") or parsed.get("node_id", "unknown"))
            node_name = node_name.replace("lab_swarm_demo-", "")
            metrics[node_name] = parsed

        except Exception as exc:
            logger.warning("Failed to process Docker logs for container %s: %s", getattr(container, "name", "?"), exc)

    return metrics


def collect_log_metrics(logs_dir: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Collect metrics from local cluster_cli log files."""
    root = Path(logs_dir or os.getenv("BLACKSWAN_LOGS_DIR", "data/cluster_runtime/latest/logs"))
    if not root.exists() or not root.is_dir():
        return {}

    metrics: dict[str, dict[str, Any]] = {}

    for log_file in sorted(root.glob("*.log")):
        try:
            text = _tail_text(log_file, max_bytes=250_000)
        except OSError as exc:
            logger.debug("Failed to read log file %s: %s", log_file, exc)
            continue

        parsed = _parse_latest_log_metrics(text)
        if not parsed:
            parsed = _parse_trade_heartbeat_log_metrics(text, default_node=log_file.stem)

        if parsed:
            node_name = str(parsed.get("node_id") or log_file.stem)
            metrics[node_name] = parsed

    return metrics


def collect_crdt_metrics(crdt_db_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """Collect latest heartbeat metrics from the local CRDT SQLite database."""
    db_path = Path(crdt_db_path or os.getenv("CRDT_DB_PATH", "data/cluster_runtime/latest/ledgers/swarm_crdt.local.db"))
    if not db_path.exists() or not db_path.is_file():
        return {}

    try:
        with sqlite3.connect(str(db_path), timeout=5.0) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT payload FROM records WHERE deleted = 0").fetchall()
    except sqlite3.Error as exc:
        logger.debug("CRDT metrics unavailable from %s: %s", db_path, exc)
        return {}

    latest_by_node: dict[str, dict[str, Any]] = {}

    for row in rows:
        payload = _decode_payload(row["payload"])
        if not isinstance(payload, dict):
            continue

        typ = payload.get("type")
        if typ not in {"trade_heartbeat", "swarm_heartbeat", "overseer_heartbeat", "security_heartbeat", "explorer_heartbeat"}:
            continue

        node_id = str(payload.get("node_id") or payload.get("node") or payload.get("agent_id") or "").strip()
        if not node_id:
            continue

        ts = _safe_float(payload.get("timestamp", payload.get("ts")), 0.0)
        current = latest_by_node.get(node_id)
        if current is not None and _safe_float(current.get("timestamp"), 0.0) >= ts:
            continue

        latest_by_node[node_id] = _heartbeat_to_metrics(payload)

    return latest_by_node


def prometheus_format(metrics: dict[str, dict[str, Any]]) -> str:
    """Convert metrics dictionary into Prometheus exposition text format."""
    lines: list[str] = []

    for metric_name, help_text, metric_type in METRIC_DEFINITIONS:
        lines.append(f"# HELP {metric_name} {help_text}")
        lines.append(f"# TYPE {metric_name} {metric_type}")

    for node in sorted(metrics):
        data = metrics[node]
        labels = _labels(node=node, swarm=str(data.get("swarm", "")), role=str(data.get("role", "")))

        lines.extend(
            [
                f'blackswan_capital{{{labels}}} {_safe_float(data.get("capital"), 0.0)}',
                f'blackswan_fitness{{{labels}}} {_safe_float(data.get("fitness"), 0.0)}',
                f'blackswan_diversity{{{labels}}} {_safe_float(data.get("diversity"), 0.0)}',
                f'blackswan_crdt_size{{{labels}}} {_safe_int(data.get("crdt_size"), 0)}',
                f'blackswan_step{{{labels}}} {_safe_int(data.get("step"), 0)}',
                f'blackswan_dq{{{labels}}} {_safe_float(data.get("dq"), 0.0)}',
                f'blackswan_niche{{{labels}}} {NICHE_MAP.get(str(data.get("niche", "exploration")), 0)}',
                f'blackswan_dry_run{{{labels}}} {1 if _truthy(data.get("dry_run")) else 0}',
                f'blackswan_execution_enabled{{{labels}}} {1 if _truthy(data.get("execution_enabled")) else 0}',
            ]
        )

    return "\n".join(lines) + "\n"


def _parse_latest_log_metrics(log_text: str) -> dict[str, Any]:
    matches = list(LOG_PATTERN.finditer(log_text))
    if not matches:
        return {}

    data = matches[-1].groupdict()
    return {
        "node_id": data["node_id"],
        "step": _safe_int(data.get("step"), 0),
        "capital": _safe_float(data.get("capital"), 0.0),
        "dq": _safe_float(data.get("dq"), 0.0),
        "fitness": _safe_float(data.get("fitness"), 0.0),
        "diversity": _safe_float(data.get("diversity"), 0.0),
        "crdt_size": _safe_int(data.get("crdt_size"), 0),
        "niche": data.get("niche", "exploration"),
    }


def _parse_trade_heartbeat_log_metrics(log_text: str, *, default_node: str) -> dict[str, Any]:
    matches = list(TRADE_HEARTBEAT_PATTERN.finditer(log_text))
    if not matches:
        return {}

    data = matches[-1].groupdict()
    return {
        "node_id": default_node,
        "swarm": "trade",
        "role": "node",
        "capital": _safe_float(data.get("capital"), 0.0),
        "dry_run": _truthy(data.get("dry_run")),
        "execution_enabled": _truthy(data.get("execution_enabled")),
    }


def _heartbeat_to_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(payload)
    nested = payload.get("metrics")
    if isinstance(nested, dict):
        metrics.update(nested)

    return {
        "node_id": str(payload.get("node_id") or payload.get("node") or payload.get("agent_id") or ""),
        "swarm": str(payload.get("swarm", "")),
        "role": str(payload.get("role", "")),
        "timestamp": _safe_float(payload.get("timestamp", payload.get("ts")), 0.0),
        "step": _safe_int(metrics.get("step", metrics.get("step_count")), 0),
        "capital": _safe_float(metrics.get("capital"), 0.0),
        "dq": _safe_float(metrics.get("dq"), 0.0),
        "fitness": _safe_float(metrics.get("fitness"), 0.0),
        "diversity": _safe_float(metrics.get("diversity"), 0.0),
        "crdt_size": _safe_int(metrics.get("crdt_size"), 0),
        "niche": str(metrics.get("niche", "exploration")),
        "dry_run": _truthy(metrics.get("dry_run")),
        "execution_enabled": _truthy(metrics.get("execution_enabled")),
    }


def _decode_payload(raw: Any) -> Any:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw


def _tail_text(path: Path, *, max_bytes: int) -> str:
    size = path.stat().st_size
    with path.open("rb") as file:
        if size > max_bytes:
            file.seek(size - max_bytes)
        return file.read().decode("utf-8", errors="replace")


def _labels(**labels: str) -> str:
    return ",".join(
        f'{key}="{_escape_label(value)}"'
        for key, value in labels.items()
        if value is not None and value != ""
    )


def _escape_label(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "enabled", "on"}
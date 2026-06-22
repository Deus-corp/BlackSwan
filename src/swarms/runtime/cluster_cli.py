from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import sqlite3
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

from uvicorn import config

from src.testing.check_memory_evidence_query_contract import (
    assert_memory_evidence_query_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RUN_DIR = PROJECT_ROOT / "data" / "cluster_runtime" / "latest"
CLUSTER_PROFILES = {
    "full-safe",
    "explorer-evidence",
    "memory-evidence",
    "explorer-memory-evidence",
}


@dataclass
class ServiceSpec:
    name: str
    module: str
    env: Dict[str, str]


@dataclass
class ManagedProcess:
    name: str
    process: asyncio.subprocess.Process
    log_path: Path
    log_handle: object


def _str_bool(value: bool) -> str:
    return "true" if bool(value) else "false"


def _csv(items: Iterable[str]) -> str:
    return ",".join(str(item).strip() for item in items if str(item).strip())


def _path(value: Path | str) -> str:
    return str(Path(value).resolve())


def _mkdirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)

def _is_valid_sqlite_db(path: Path) -> bool:
    if not path.exists():
        return True

    if path.is_dir():
        return False

    if path.stat().st_size == 0:
        return True

    try:
        con = sqlite3.connect(str(path))
        con.execute("PRAGMA schema_version")
        con.close()
        return True
    except sqlite3.DatabaseError:
        return False


def _prepare_sqlite_file(path: Path, *, reset_invalid: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and not _is_valid_sqlite_db(path):
        if not reset_invalid:
            raise RuntimeError(f"Invalid SQLite database file: {path}")
        backup = path.with_suffix(path.suffix + f".bad.{int(time.time())}")
        path.rename(backup)
        print(f"⚠ moved invalid sqlite file: {path} -> {backup}")

    con = sqlite3.connect(str(path), timeout=30)
    try:
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("PRAGMA busy_timeout=30000;")
        con.commit()
    finally:
        con.close()

def _prepare_run_storage(args: argparse.Namespace, run_dir: Path) -> None:
    ledger_dir = run_dir / "ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)

    crdt_db = ledger_dir / args.crdt_db_name
    event_db = ledger_dir / args.event_sqlite_name

    _prepare_sqlite_file(crdt_db, reset_invalid=True)
    _prepare_sqlite_file(event_db, reset_invalid=True)

    # Initialize CRDT schema in the parent process before children race on it.
    try:
        from src.core.crdt_layer import CRDTStorage

        CRDTStorage(str(crdt_db))
        print(f"✅ pre-initialized CRDT sqlite: {crdt_db}")
    except Exception as exc:
        print(f"⚠ CRDT pre-init failed for {crdt_db}: {exc}")
        raise

def _apply_if_present(env: Dict[str, str], key: str, value: Optional[str]) -> None:
    if value is not None and str(value).strip():
        env[key] = str(value).strip()


def _base_env(args: argparse.Namespace, run_dir: Path) -> Dict[str, str]:
    ledger_dir = run_dir / "ledgers"
    nonce_dir = run_dir / "nonce"
    memory_dir = run_dir / "memory"
    meta_dir = run_dir / "meta_agent"

    _mkdirs(run_dir, ledger_dir, nonce_dir, memory_dir, meta_dir, run_dir / "logs")

    env = dict(os.environ)

    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    # Runtime identity / storage.
    env["CLUSTER_RUN_DIR"] = str(run_dir)
    env["CRDT_DB_PATH"] = str(ledger_dir / args.crdt_db_name)
    env["EVENT_LEDGER_PATH"] = str(ledger_dir / args.event_ledger_name)
    env["EVENT_SQLITE_PATH"] = str(ledger_dir / args.event_sqlite_name)
    env["NONCE_DB_PATH"] = str(nonce_dir / "nonce.db")

    # Some project modules may still use these conventional data paths.
    env["META_AGENT_DATA_DIR"] = str(meta_dir)
    env["MEMORY_DIR"] = str(memory_dir)

    # Core runtime flags.
    env["TOTAL_NODES"] = str(args.trade_nodes)
    env["TOTAL_TRADE_NODES"] = str(args.trade_nodes)
    env["TOTAL_MEMORY_NODES"] = str(args.memory_nodes)
    env["TOTAL_SIMULATION_NODES"] = str(args.simulation_nodes)
    env["LOG_LEVEL"] = args.log_level
    env["GOSSIP_SIGNING_ENABLED"] = _str_bool(args.gossip_signing_enabled)
    env["MEMORY_API_ENABLED"] = _str_bool(args.memory_api_enabled)
    env["OVERSEER_COORDINATION_INTERVAL_SECONDS"] = str(args.overseer_interval)

    # Trading/runtime defaults.
    env["MARKET_MODE"] = args.market_mode
    env["TRADING_SYMBOLS"] = args.trading_symbols
    env["TEST_WEB3_SWAP_AMOUNT"] = str(args.test_web3_swap_amount)
    env["TEST_WEB3_SWAP_SIDE"] = args.test_web3_swap_side
    env["WEB3_POOL_FEE"] = str(args.web3_pool_fee)
    env["PRICE_SCALE"] = str(args.price_scale)
    env["MIN_WETH_BALANCE"] = str(args.min_weth_balance)
    env["MIN_ETH_BALANCE"] = str(args.min_eth_balance)
    env["MAX_USDC_BALANCE"] = str(args.max_usdc_balance)

    # Risk/economy defaults.
    env["BURN_RATE"] = str(args.burn_rate)
    env["FAILURE_PROB"] = str(args.failure_prob)
    env["CAPITAL_ALERT_THRESHOLD"] = str(args.capital_alert_threshold)
    env["HEDGE_RATIO"] = str(args.hedge_ratio)

    # Optional integration flags.
    env["INTERNET_RESEARCHER_ENABLED"] = _str_bool(args.internet_researcher_enabled)
    env["TRADINGVIEW_WEBHOOK_ENABLED"] = _str_bool(args.tradingview_webhook_enabled)
    env["TRADINGVIEW_WEBHOOK_PORT"] = str(args.tradingview_webhook_port)
    env["ORDERBOOK_ANALYSIS_ENABLED"] = _str_bool(args.orderbook_analysis_enabled)
    env["HEDGE_ENABLED"] = _str_bool(args.hedge_enabled)

    # Execution safety.
    if args.safe:
        env["EXECUTION_ENABLED"] = "false"
        env["DRY_RUN"] = "true"
        env["TRADINGVIEW_WEBHOOK_ENABLED"] = "false"
        env["HEDGE_ENABLED"] = "false"
        env["ORDERBOOK_ANALYSIS_ENABLED"] = "false"
        env["INTERNET_RESEARCHER_ENABLED"] = "false"
    else:
        env["EXECUTION_ENABLED"] = _str_bool(args.execution_enabled)
        env["DRY_RUN"] = _str_bool(args.dry_run)

    # Pass-through secrets / provider settings from host/devcontainer.
    passthrough_keys = [
        "WEB3_RPC_URL",
        "WEB3_PRIVATE_KEY",
        "BINANCE_TESTNET_API_KEY",
        "BINANCE_TESTNET_API_SECRET",
        "ETHERSCAN_API_KEY",
        "GROQ_API_KEY",
        "DEEPSEEK_API_KEY",
        "GEMINI_API_KEY",
        "GEMINI_API_KEYS",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "GOSSIP_SIGNING_KEY",
    ]
    for key in passthrough_keys:
        if key in os.environ and os.environ[key]:
            env[key] = os.environ[key]

    # Explicit CLI overrides.
    _apply_if_present(env, "WEB3_RPC_URL", args.web3_rpc_url)
    _apply_if_present(env, "WEB3_PRIVATE_KEY", args.web3_private_key)
    _apply_if_present(env, "GROQ_API_KEY", args.groq_api_key)
    _apply_if_present(env, "TELEGRAM_BOT_TOKEN", args.telegram_bot_token)
    _apply_if_present(env, "TELEGRAM_CHAT_ID", args.telegram_chat_id)

    return env


def _trade_env(base: Mapping[str, str], args: argparse.Namespace, idx: int) -> Dict[str, str]:
    env = dict(base)
    port = args.base_port + idx - 1

    env["NODE_ID"] = f"{args.trade_node_prefix}-{idx}"
    env["NODE_INDEX"] = str(idx)
    env["PORT"] = str(port)
    env["GOSSIP_PORT"] = str(port)

    peers = [
        f"http://127.0.0.1:{args.base_port + peer_idx - 1}"
        for peer_idx in range(1, args.trade_nodes + 1)
        if peer_idx != idx
    ]
    env["PEERS"] = _csv(peers)

    # Avoid port conflicts when several local trade nodes are launched.
    if env.get("TRADINGVIEW_WEBHOOK_ENABLED", "false").lower() == "true":
        env["TRADINGVIEW_WEBHOOK_PORT"] = str(args.tradingview_webhook_port + idx - 1)

    return env


def _service_env(base: Mapping[str, str], node_id: str) -> Dict[str, str]:
    env = dict(base)
    env["NODE_ID"] = node_id
    return env

def _memory_env(base: Mapping[str, str], args: argparse.Namespace, idx: int) -> Dict[str, str]:
    env = dict(base)
    node_id = f"{args.memory_node_prefix}-{idx}"
    env["NODE_ID"] = node_id
    env["MEMORY_NODE_ID"] = node_id
    env["MEMORY_HEARTBEAT_INTERVAL_SECONDS"] = str(args.memory_heartbeat_interval)
    env["MEMORY_INGEST_RECORDS_SINCE_START"] = "true" if args.memory_ingest_since_start else "false"
    env["MEMORY_INGEST_SWARM_EVENTS"] = "true" if args.memory_ingest_swarm_events else "false"
    return env


def _simulation_env(base: Mapping[str, str], args: argparse.Namespace, idx: int) -> Dict[str, str]:
    env = dict(base)
    node_id = f"{args.simulation_node_prefix}-{idx}"
    env["NODE_ID"] = node_id
    env["SIMULATION_NODE_ID"] = node_id
    env["SIMULATION_HEARTBEAT_INTERVAL_SECONDS"] = str(args.simulation_heartbeat_interval)
    return env

def _apply_profile_defaults(args: argparse.Namespace) -> None:
    """Apply curated local cluster profiles before service construction.

    Profiles are development/runtime UX shortcuts. Explicit safety remains
    conservative: profiles force safe mode unless the operator also passes
    --unsafe.
    """
    profile = str(getattr(args, "profile", "") or "full-safe").strip()

    if profile not in CLUSTER_PROFILES:
        raise ValueError(f"Unsupported cluster profile: {profile}")

    if profile == "full-safe":
        return

    # Evidence-oriented profiles should not start trading by default.
    args.no_trade = True
    args.with_trade_meta = False
    args.no_trade_meta = True

    # Keep these profiles advisory-only unless operator explicitly passed --unsafe.
    if bool(getattr(args, "safe", True)):
        args.execution_enabled = False
        args.dry_run = True
        args.tradingview_webhook_enabled = False
        args.hedge_enabled = False
        args.orderbook_analysis_enabled = False
        args.internet_researcher_enabled = False

    if profile == "explorer-evidence":
        args.no_security = True
        args.no_security_meta = True
        args.no_explorer = False
        args.no_explorer_meta = False
        args.memory_nodes = 0
        args.simulation_nodes = 0
        args.no_overseer = True
        return

    if profile == "memory-evidence":
        args.no_security = True
        args.no_security_meta = True
        args.no_explorer = True
        args.no_explorer_meta = True
        args.memory_nodes = max(1, int(args.memory_nodes or 0))
        args.simulation_nodes = 0
        args.no_overseer = True
        args.memory_ingest_since_start = False
        return

    if profile == "explorer-memory-evidence":
        args.no_security = True
        args.no_security_meta = True
        args.no_explorer = False
        args.no_explorer_meta = False
        args.memory_nodes = max(1, int(args.memory_nodes or 0))
        args.simulation_nodes = 0
        args.no_overseer = True
        args.memory_ingest_since_start = False
        return


def _build_services(args: argparse.Namespace, run_dir: Path) -> List[ServiceSpec]:
    base = _base_env(args, run_dir)

    if args.fresh_crdt:
        _fresh_runtime_ledgers(run_dir, base)

    services: List[ServiceSpec] = []

    if not args.no_trade:
        for idx in range(1, args.trade_nodes + 1):
            services.append(
                ServiceSpec(
                    name=f"trade-{idx}",
                    module="src.swarms.trade.node",
                    env=_trade_env(base, args, idx),
                )
            )

    if args.with_trade_meta and not args.no_trade_meta:
        services.append(
            ServiceSpec(
                name="trade-meta",
                module="src.swarms.trade.meta_agent",
                env=_service_env(base, "trade-meta-local"),
            )
        )

    if not args.no_security:
        services.append(
            ServiceSpec(
                name="security-node",
                module="src.swarms.security.node",
                env=_service_env(base, "security-local"),
            )
        )

    if not args.no_security_meta:
        services.append(
            ServiceSpec(
                name="security-meta",
                module="src.swarms.security.meta_agent",
                env=_service_env(base, "security-meta-local"),
            )
        )

    if not args.no_explorer:
        services.append(
            ServiceSpec(
                name="explorer-node",
                module="src.swarms.explorer.node",
                env=_service_env(base, "explorer-local"),
            )
        )

    if not args.no_explorer_meta:
        services.append(
            ServiceSpec(
                name="explorer-meta",
                module="src.swarms.explorer.meta_agent",
                env=_service_env(base, "explorer-meta-local"),
            )
        )

    for idx in range(1, args.memory_nodes + 1):
        services.append(
            ServiceSpec(
                name=f"memory-{idx}",
                module="src.swarms.memory.node",
                env=_memory_env(base, args, idx),
            )
        )

    for idx in range(1, args.simulation_nodes + 1):
        services.append(
            ServiceSpec(
                name=f"simulation-{idx}",
                module="src.swarms.simulation.node",
                env=_simulation_env(base, args, idx),
            )
        )

    if not args.no_overseer:
        services.append(
            ServiceSpec(
                name="overseer",
                module="src.swarms.overseer.node",
                env=_service_env(base, "overseer-local"),
            )
        )

    if args.with_improver:
        env = _service_env(base, "improver-local")
        _apply_if_present(env, "GEMINI_MODELS", args.improver_gemini_models)
        _apply_if_present(env, "GEMINI_CRITIC_MODELS", args.improver_gemini_critic_models)
        env["IMPROVER_CLUSTER_RUN"] = "true"
        services.append(
            ServiceSpec(
                name="improver",
                module="src.swarms.improver.improver_agent_core.cli",
                env=env,
            )
        )

    return services


async def _spawn(spec: ServiceSpec, log_dir: Path, echo: bool = False) -> ManagedProcess:
    log_path = log_dir / f"{spec.name}.log"
    log_handle = log_path.open("ab", buffering=0)

    print(f"▶ starting {spec.name:<15} python -m {spec.module}")
    print(f"  log: {log_path}")

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-m",
        spec.module,
        cwd=str(PROJECT_ROOT),
        env=spec.env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE if echo else log_handle,
        stderr=asyncio.subprocess.STDOUT,
    )

    item = ManagedProcess(
        name=spec.name,
        process=process,
        log_path=log_path,
        log_handle=log_handle,
    )

    if echo:
        asyncio.create_task(_echo_stdout(item, log_handle), name=f"log:{spec.name}")

    return item


async def _echo_stdout(item: ManagedProcess, log_handle: object) -> None:
    if item.process.stdout is None:
        return

    while True:
        line = await item.process.stdout.readline()
        if not line:
            break
        log_handle.write(line)
        print(f"[{item.name}] {line.decode(errors='replace').rstrip()}")


async def _terminate(processes: List[ManagedProcess], timeout: float = 20.0) -> None:
    if not processes:
        return

    print("⏹ stopping cluster...")

    for item in processes:
        if item.process.returncode is None:
            try:
                item.process.send_signal(signal.SIGINT)
            except ProcessLookupError:
                pass

    try:
        await asyncio.wait_for(
            asyncio.gather(
                *(item.process.wait() for item in processes),
                return_exceptions=True,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        print("⚠ graceful SIGINT timed out; sending SIGTERM")
        for item in processes:
            if item.process.returncode is None:
                try:
                    item.process.terminate()
                except ProcessLookupError:
                    pass

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *(item.process.wait() for item in processes),
                    return_exceptions=True,
                ),
                timeout=8.0,
            )
        except asyncio.TimeoutError:
            print("⚠ SIGTERM timed out; sending SIGKILL")
            for item in processes:
                if item.process.returncode is None:
                    try:
                        item.process.kill()
                    except ProcessLookupError:
                        pass

    for item in processes:
        try:
            item.log_handle.close()
        except Exception:
            pass


async def _monitor_processes(
    processes: List[ManagedProcess],
    stop_event: asyncio.Event,
    *,
    strict: bool,
) -> None:
    reported: set[str] = set()

    while not stop_event.is_set():
        for item in processes:
            rc = item.process.returncode
            if rc is not None and item.name not in reported:
                reported.add(item.name)
                print(f"⚠ service exited: {item.name} returncode={rc} log={item.log_path}")

                if strict:
                    stop_event.set()
                    return

        await asyncio.sleep(1.0)


def _write_run_metadata(args: argparse.Namespace, run_dir: Path, services: List[ServiceSpec]) -> None:
    metadata_path = run_dir / "cluster_run.env"
    lines = [
        f"RUN_DIR={run_dir}",
        f"PROJECT_ROOT={PROJECT_ROOT}",
        f"PROFILE={getattr(args, 'profile', 'full-safe')}",
        f"SAFE={args.safe}",
        f"DURATION={args.duration}",
        f"TRADE_NODES={args.trade_nodes}",
        f"MEMORY_NODES={args.memory_nodes}",
        f"SIMULATION_NODES={args.simulation_nodes}",
        f"CRDT_DB_PATH={run_dir / 'ledgers' / args.crdt_db_name}",
        f"EVENT_LEDGER_PATH={run_dir / 'ledgers' / args.event_ledger_name}",
        f"EVENT_SQLITE_PATH={run_dir / 'ledgers' / args.event_sqlite_name}",
        "SERVICES=" + ",".join(spec.name for spec in services),
        "",
    ]
    metadata_path.write_text("\n".join(lines), encoding="utf-8")


async def run_up(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()

    _apply_profile_defaults(args)

    if args.clean and run_dir.exists():
        import shutil
        shutil.rmtree(run_dir)

    log_dir = run_dir / "logs"
    _mkdirs(log_dir)

    _prepare_run_storage(args, run_dir)

    services = _build_services(args, run_dir)
    if not services:
        print("No services selected.")
        return 2

    _write_run_metadata(args, run_dir, services)

    print("BlackSwan local cluster")
    print(f"  project: {PROJECT_ROOT}")
    print(f"  run_dir: {run_dir}")
    print(f"  safe:    {args.safe}")
    print(f"  services:{', '.join(spec.name for spec in services)}")

    processes: List[ManagedProcess] = []
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            pass

    try:
        for spec in services:
            item = await _spawn(spec, log_dir=log_dir, echo=args.echo)
            processes.append(item)
            if args.start_delay > 0:
                await asyncio.sleep(args.start_delay)

        monitor_task = asyncio.create_task(
            _monitor_processes(processes, stop_event, strict=args.strict),
            name="cluster_monitor",
        )

        print(f"✅ cluster started: {len(processes)} process(es)")
        print(f"📄 logs: {log_dir}")
        print(f"🧬 crdt: {run_dir / 'ledgers' / args.crdt_db_name}")

        if args.duration and args.duration > 0:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=args.duration)
            except asyncio.TimeoutError:
                pass
        else:
            await stop_event.wait()

        monitor_task.cancel()
        await _terminate(processes, timeout=args.stop_timeout)

        print("✅ cluster stopped")
        return 0

    except Exception as exc:
        print(f"❌ cluster failed: {exc}")
        await _terminate(processes, timeout=args.stop_timeout)
        return 1


def _tail_file(path: Path, lines: int) -> List[str]:
    if not path.exists():
        return []
    data = path.read_text(errors="replace").splitlines()
    return data[-lines:]


def run_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    log_dir = run_dir / "logs"

    print(f"run_dir: {run_dir}")
    print(f"logs: {log_dir}")

    metadata = run_dir / "cluster_run.env"
    if metadata.exists():
        print("\n== cluster_run.env ==")
        print(metadata.read_text(errors="replace").strip())

    if log_dir.exists():
        print("\n== logs ==")
        for path in sorted(log_dir.glob("*.log")):
            print(f"{path.name:28} {path.stat().st_size:>10} bytes")

    ledger_dir = run_dir / "ledgers"
    if ledger_dir.exists():
        print("\n== ledgers ==")
        for path in sorted(ledger_dir.iterdir()):
            if path.is_file():
                print(f"{path.name:28} {path.stat().st_size:>10} bytes")

    return 0


def run_logs(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    log_dir = run_dir / "logs"

    names = args.services or []
    if not names:
        paths = sorted(log_dir.glob("*.log"))
    else:
        paths = [log_dir / f"{name}.log" for name in names]

    for path in paths:
        print(f"\n== {path} ==")
        for line in _tail_file(path, args.tail):
            print(line)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local BlackSwan swarm cluster inside the devcontainer."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    up = sub.add_parser("up", help="Start a local bounded swarm cluster.")

    # Runtime selection.
    up.add_argument("--all", action="store_true", default=True, help="Start the default full safe cluster.")
    up.add_argument("--trade-nodes", type=int, default=1, help="Number of local trade nodes.")

    up.add_argument("--memory-nodes", type=int, default=0, help="Number of local memory swarm nodes.")
    up.add_argument("--memory-node-prefix", default="memory", help="Prefix for generated memory node ids.")
    up.add_argument(
        "--memory-heartbeat-interval",
        type=float,
        default=30.0,
        help="Memory swarm heartbeat interval in seconds.",
    )
    up.add_argument(
        "--fresh-crdt",
        action="store_true",
        help="Delete local CRDT database files before starting the cluster. Development only.",
    )
    up.add_argument(
        "--memory-ingest-since-start",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Memory nodes ingest only CRDT records created after node start. Use --no-memory-ingest-since-start to reindex old records.",
    )
    up.add_argument(
        "--memory-ingest-swarm-events",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Allow memory nodes to ingest generic swarm_event records. Disabled by default.",
    )

    up.add_argument("--simulation-nodes", type=int, default=0, help="Number of local simulation swarm nodes.")
    up.add_argument("--simulation-node-prefix", default="simulation", help="Prefix for generated simulation node ids.")
    up.add_argument(
        "--simulation-heartbeat-interval",
        type=float,
        default=30.0,
        help="Simulation swarm heartbeat interval in seconds.",
    )
    up.add_argument(
        "--overseer-interval",
        type=float,
        default=10,
        help="Overseer coordination interval in seconds for local cluster runs.",
    )
    up.add_argument("--trade-node-prefix", default="trade", help="Prefix for generated trade node ids.")
    up.add_argument("--base-port", type=int, default=9777, help="Base gossip port for local trade nodes.")
    up.add_argument("--duration", type=float, default=120.0, help="Run duration in seconds. Use 0 for until Ctrl+C.")
    up.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR, help="Runtime directory for ledgers/logs.")
    up.add_argument("--clean", action="store_true", default=True, help="Clear run-dir before starting.")
    up.add_argument("--no-clean", dest="clean", action="store_false", help="Reuse existing run-dir.")
    up.add_argument("--echo", action="store_true", help="Echo subprocess logs to console as well as files.")
    up.add_argument("--start-delay", type=float, default=1.5, help="Delay between service starts.")
    up.add_argument("--stop-timeout", type=float, default=20.0, help="Graceful shutdown timeout.")

    up.add_argument(
        "--profile",
        choices=sorted(CLUSTER_PROFILES),
        default="full-safe",
        help=(
            "Curated local cluster profile. "
            "full-safe preserves existing defaults; explorer-evidence starts "
            "explorer node/meta only; memory-evidence starts memory node(s); "
            "explorer-memory-evidence starts explorer plus memory ingestion."
        ),
    )

    # Service toggles.
    up.add_argument("--no-trade", action="store_true")
    up.add_argument("--with-trade-meta", action="store_true", help="Start legacy trade meta-agent.")
    up.add_argument("--no-trade-meta", action="store_true")
    up.add_argument("--no-security", action="store_true")
    up.add_argument("--no-security-meta", action="store_true")
    up.add_argument("--no-explorer", action="store_true")
    up.add_argument("--no-explorer-meta", action="store_true")
    up.add_argument("--no-overseer", action="store_true")
    up.add_argument("--with-improver", action="store_true", help="Start ImproverAgent too. Disabled by default.")

    # Safety / trading.
    up.add_argument("--safe", action="store_true", default=True, help="Force dry-run/no-execution safety mode.")
    up.add_argument("--unsafe", dest="safe", action="store_false", help="Allow explicit execution flags.")
    up.add_argument("--execution-enabled", action="store_true", default=False)
    up.add_argument("--dry-run", action="store_true", default=True)
    up.add_argument("--market-mode", default="web3", choices=["sim", "web3", "live", "futures"])
    up.add_argument("--trading-symbols", default="WETH/USDC")
    up.add_argument("--test-web3-swap-amount", type=float, default=0.0005)
    up.add_argument("--test-web3-swap-side", default="sell", choices=["buy", "sell"])
    up.add_argument("--web3-pool-fee", type=int, default=3000)
    up.add_argument("--price-scale", type=float, default=10000)
    up.add_argument("--min-weth-balance", type=float, default=0.0001)
    up.add_argument("--min-eth-balance", type=float, default=0.002)
    up.add_argument("--max-usdc-balance", type=float, default=0.5)

    # Optional integrations.
    up.add_argument("--tradingview-webhook-enabled", action="store_true", default=False)
    up.add_argument("--tradingview-webhook-port", type=int, default=8888)
    up.add_argument("--internet-researcher-enabled", action="store_true", default=False)
    up.add_argument("--orderbook-analysis-enabled", action="store_true", default=False)
    up.add_argument("--hedge-enabled", action="store_true", default=False)
    up.add_argument("--hedge-ratio", type=float, default=0.5)
    up.add_argument("--memory-api-enabled", action="store_true", default=False)
    up.add_argument("--gossip-signing-enabled", action="store_true", default=True)

    # Economy/risk.
    up.add_argument("--burn-rate", type=float, default=0.0)
    up.add_argument("--failure-prob", type=float, default=0.0)
    up.add_argument("--capital-alert-threshold", type=float, default=100.0)

    # Storage.
    up.add_argument("--crdt-db-name", default="swarm_crdt.local.db")
    up.add_argument("--event-ledger-name", default="events.local.jsonl")
    up.add_argument("--event-sqlite-name", default="events.local.db")

    # Secrets / overrides.
    up.add_argument("--web3-rpc-url", default=None)
    up.add_argument("--web3-private-key", default=None)
    up.add_argument("--groq-api-key", default=None)
    up.add_argument("--telegram-bot-token", default=None)
    up.add_argument("--telegram-chat-id", default=None)

    # Improver-specific optional route.
    up.add_argument("--improver-gemini-models", default=None)
    up.add_argument("--improver-gemini-critic-models", default=None)

    # Logs/config.
    up.add_argument("--log-level", default="INFO")

    up.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Stop the cluster when any service exits.",
    )
    up.add_argument(
        "--no-strict",
        dest="strict",
        action="store_false",
        help="Keep the cluster running when a service exits.",
    )

    status = sub.add_parser("status", help="Show latest run files and metadata.")
    status.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)

    logs = sub.add_parser("logs", help="Tail logs from the latest run.")
    logs.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    logs.add_argument("--tail", type=int, default=120)
    logs.add_argument("services", nargs="*", help="Service names, e.g. trade-1 overseer")

    memory_query = sub.add_parser(
        "memory-query",
        help="Run local memory evidence catalog query and optional contract smoke.",
    )
    memory_query.add_argument("--text-query", default="agents memory")
    memory_query.add_argument("--limit", type=int, default=5)
    memory_query.add_argument("--json", action="store_true", default=True)

    memory_query.add_argument(
        "--json-output",
        default="",
        help="Optional path to write memory query JSON result.",
    )
    memory_query.add_argument(
        "--check-contract",
        action="store_true",
        help="Validate memory query JSON against the evidence query contract.",
    )
    memory_replay_query = sub.add_parser(
        "memory-replay-query",
        help=(
            "Replay explorer useful evidence memory records into a memory "
            "catalog query and optional contract smoke."
        ),
    )
    memory_replay_smoke = sub.add_parser(
        "memory-replay-smoke",
        help=(
            "Run one-command explorer runtime + memory replay contract smoke."
        ),
    )
    memory_replay_latest = sub.add_parser(
        "memory-replay-latest",
        help="Inspect latest explorer memory replay smoke artifact.",
    )
    latest_artifacts = sub.add_parser(
        "latest-artifacts",
        help="Inspect cluster latest runtime artifacts index.",
    )
    latest_artifacts_cleanup = sub.add_parser(
        "latest-artifacts-cleanup",
        help="Dry-run cleanup inspector for cluster latest artifacts.",
    )
    latest_artifacts_cleanup.add_argument(
        "--artifacts-root",
        default="",
        help=(
            "Directory containing latest artifact JSON files. Defaults to "
            "data/cluster_runtime/latest/artifacts."
        ),
    )
    latest_artifacts_cleanup.add_argument(
        "--retention-max-age-days",
        type=float,
        default=0.0,
        help=(
            "Dry-run retention threshold in days. Reports would-delete "
            "artifacts without deleting files."
        ),
    )
    latest_artifacts_cleanup.add_argument(
        "--retention-max-age-seconds",
        type=float,
        default=0.0,
        help=(
            "Dry-run retention threshold in seconds. Overrides days when "
            "provided. No files are deleted."
        ),
    )
    latest_artifacts_cleanup.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Explicit dry-run flag. This command never deletes files.",
    )
    latest_artifacts_cleanup.add_argument(
        "--execute-delete-local-artifacts",
        action="store_true",
        default=False,
        help=(
            "Execute deletion of stale local latest artifacts from the "
            "allowlisted latest/artifacts root."
        ),
    )
    latest_artifacts_cleanup.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print machine-readable JSON summary.",
    )
    latest_artifacts_cleanup.add_argument(
        "--check-contract",
        action="store_true",
        help="Exit with code 1 unless the cleanup dry-run contract is valid.",
    )
    latest_artifacts.add_argument(
        "--artifacts-root",
        default="",
        help=(
            "Directory containing latest artifact JSON files. Defaults to "
            "data/cluster_runtime/latest/artifacts."
        ),
    )
    latest_artifacts.add_argument(
        "--retention-max-age-days",
        type=float,
        default=0.0,
        help=(
            "Inspect-only retention threshold in days. Reports stale artifacts "
            "without deleting files."
        ),
    )
    latest_artifacts.add_argument(
        "--retention-max-age-seconds",
        type=float,
        default=0.0,
        help=(
            "Inspect-only retention threshold in seconds. Overrides days when "
            "provided. Reports stale artifacts without deleting files."
        ),
    )
    latest_artifacts.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print machine-readable JSON summary.",
    )
    latest_artifacts.add_argument(
        "--check-contract",
        action="store_true",
        help="Exit with code 1 unless all indexed artifact contracts are valid.",
    )
    memory_replay_latest.add_argument(
        "--json-path",
        default="",
        help="Explicit explorer memory replay smoke JSON artifact path.",
    )
    memory_replay_latest.add_argument(
        "--search-root",
        action="append",
        default=[],
        help=(
            "Directory or file to search. Can be passed multiple times. "
            "Defaults to /tmp and data/cluster_runtime/latest."
        ),
    )
    memory_replay_latest.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print machine-readable JSON summary.",
    )
    memory_replay_latest.add_argument(
        "--check-contract",
        action="store_true",
        help="Exit with code 1 unless the latest artifact contract is valid.",
    )
    memory_replay_smoke.add_argument(
        "--goal",
        default="autonomous agents memory systems",
        help="Explorer research goal.",
    )
    memory_replay_smoke.add_argument(
        "--exploration-run-id",
        default="exp-run-memory-replay-smoke",
        help="Explorer runtime smoke run id.",
    )
    memory_replay_smoke.add_argument("--ticks", type=int, default=3)
    memory_replay_smoke.add_argument(
        "--source-adapter",
        action="append",
        default=None,
        help=(
            "Source adapter to seed. Can be passed multiple times. "
            "Default is github, arxiv, search, sitemap."
        ),
    )
    memory_replay_smoke.add_argument(
        "--no-source-plan",
        action="store_true",
        default=False,
        help="Disable source-plan seeding.",
    )
    memory_replay_smoke.add_argument(
        "--memory-replay-artifact-limit",
        type=int,
        default=20,
        help="Maximum replayable memory records embedded by explorer runtime.",
    )
    memory_replay_smoke.add_argument(
        "--text-query",
        default="agents memory",
        help="Memory replay query text.",
    )
    memory_replay_smoke.add_argument("--limit", type=int, default=5)
    memory_replay_smoke.add_argument(
        "--work-dir",
        default="",
        help="Optional directory for intermediate explorer/replay artifacts.",
    )
    memory_replay_smoke.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep temporary artifacts when --work-dir is not provided.",
    )
    memory_replay_smoke.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Print full JSON smoke summary.",
    )
    memory_replay_smoke.add_argument(
        "--json-output",
        default="",
        help="Optional path to write smoke summary JSON.",
    )
    memory_replay_smoke.add_argument(
        "--write-latest",
        action="store_true",
        default=False,
        help=(
            "Also write the smoke summary to "
            "data/cluster_runtime/latest/artifacts/"
            "explorer_memory_replay_smoke.json."
        ),
    )
    memory_replay_smoke.add_argument(
        "--check-contract",
        action="store_true",
        help="Print explicit explorer memory replay smoke contract confirmation.",
    )
    memory_replay_query.add_argument(
        "--db-path",
        default=str(DEFAULT_RUN_DIR / "ledgers" / "swarm_crdt.local.db"),
        help="Path to CRDT sqlite database to scan.",
    )
    memory_replay_query.add_argument(
        "--json-input",
        default="",
        help="Optional JSON file to scan for explorer memory records.",
    )
    memory_replay_query.add_argument(
        "--text-query",
        default="agents memory",
        help="Text query for deterministic replay catalog filtering.",
    )
    memory_replay_query.add_argument("--limit", type=int, default=5)
    memory_replay_query.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Print full JSON replay query result.",
    )
    memory_replay_query.add_argument(
        "--json-output",
        default="",
        help="Optional path to write replay query JSON result.",
    )
    memory_replay_query.add_argument(
        "--check-contract",
        action="store_true",
        help="Validate replay query JSON against the memory evidence query contract.",
    )

    return parser


def run_latest_artifacts_cleanup(args: argparse.Namespace) -> int:
    """Run dry-run cleanup inspector for cluster latest artifacts."""
    command = [
        sys.executable,
        "-m",
        "src.testing.cleanup_cluster_latest_artifacts",
    ]

    artifacts_root = str(getattr(args, "artifacts_root", "") or "").strip()
    if artifacts_root:
        command.extend(["--artifacts-root", artifacts_root])

    retention_max_age_seconds = float(
        getattr(args, "retention_max_age_seconds", 0.0) or 0.0
    )
    if retention_max_age_seconds > 0.0:
        command.extend(
            [
                "--retention-max-age-seconds",
                str(retention_max_age_seconds),
            ]
        )
    else:
        retention_max_age_days = float(
            getattr(args, "retention_max_age_days", 0.0) or 0.0
        )
        if retention_max_age_days > 0.0:
            command.extend(
                [
                    "--retention-max-age-days",
                    str(retention_max_age_days),
                ]
            )

    if bool(getattr(args, "dry_run", False)):
        command.append("--dry-run")
    
    if bool(getattr(args, "execute_delete_local_artifacts", False)):
        command.append("--execute-delete-local-artifacts")

    if bool(getattr(args, "json", False)):
        command.append("--json")

    if bool(getattr(args, "check_contract", False)):
        command.append("--check-contract")

    print("Dry-run cleanup cluster latest artifacts:")
    print(" ".join(command))

    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        check=False,
        text=True,
    )

    return int(completed.returncode or 0)


def run_latest_artifacts(args: argparse.Namespace) -> int:
    """Inspect cluster latest runtime artifacts index."""
    command = [
        sys.executable,
        "-m",
        "src.testing.inspect_cluster_latest_artifacts",
    ]

    artifacts_root = str(getattr(args, "artifacts_root", "") or "").strip()
    if artifacts_root:
        command.extend(["--artifacts-root", artifacts_root])

    if bool(getattr(args, "json", False)):
        command.append("--json")

    if bool(getattr(args, "check_contract", False)):
        command.append("--check-contract")

    print("Inspect cluster latest artifacts:")
    print(" ".join(command))

    retention_max_age_seconds = float(
        getattr(args, "retention_max_age_seconds", 0.0) or 0.0
    )
    if retention_max_age_seconds > 0.0:
        command.extend(
            [
                "--retention-max-age-seconds",
                str(retention_max_age_seconds),
            ]
        )
    else:
        retention_max_age_days = float(
            getattr(args, "retention_max_age_days", 0.0) or 0.0
        )
        if retention_max_age_days > 0.0:
            command.extend(
                [
                    "--retention-max-age-days",
                    str(retention_max_age_days),
                ]
            )

    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        check=False,
        text=True,
    )

    return int(completed.returncode or 0)


def run_memory_replay_latest(args: argparse.Namespace) -> int:
    """Inspect latest explorer memory replay smoke artifact."""
    command = [
        sys.executable,
        "-m",
        "src.testing.inspect_memory_replay_smoke_latest",
    ]

    json_path = str(getattr(args, "json_path", "") or "").strip()
    if json_path:
        command.extend(["--json-path", json_path])

    for search_root in list(getattr(args, "search_root", []) or []):
        command.extend(["--search-root", str(search_root)])

    if bool(getattr(args, "json", False)):
        command.append("--json")

    if bool(getattr(args, "check_contract", False)):
        command.append("--check-contract")

    print("Inspect latest memory replay smoke artifact:")
    print(" ".join(command))

    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        check=False,
        text=True,
    )

    return int(completed.returncode or 0)


def run_memory_replay_smoke(args: argparse.Namespace) -> int:
    """Run one-command explorer runtime + memory replay contract smoke."""
    command = [
        sys.executable,
        "-m",
        "src.testing.run_explorer_memory_replay_smoke",
        "--goal",
        str(getattr(args, "goal", "") or "autonomous agents memory systems"),
        "--exploration-run-id",
        str(
            getattr(args, "exploration_run_id", "")
            or "exp-run-memory-replay-smoke"
        ),
        "--ticks",
        str(max(0, int(getattr(args, "ticks", 3) or 3))),
        "--memory-replay-artifact-limit",
        str(
            max(
                0,
                int(getattr(args, "memory_replay_artifact_limit", 20) or 20),
            )
        ),
        "--text-query",
        str(getattr(args, "text_query", "") or "agents memory"),
        "--limit",
        str(max(0, int(getattr(args, "limit", 5) or 5))),
    ]

    if bool(getattr(args, "no_source_plan", False)):
        command.append("--no-source-plan")

    source_adapters = list(getattr(args, "source_adapter", None) or [])
    for adapter in source_adapters:
        command.extend(["--source-adapter", str(adapter)])

    work_dir = str(getattr(args, "work_dir", "") or "").strip()
    if work_dir:
        command.extend(["--work-dir", work_dir])

    if bool(getattr(args, "keep_artifacts", False)):
        command.append("--keep-artifacts")

    if bool(getattr(args, "json", False)):
        command.append("--json")

    json_output = str(getattr(args, "json_output", "") or "").strip()
    if json_output:
        command.extend(["--json-output", json_output])
    
    if bool(getattr(args, "write_latest", False)):
        command.append("--write-latest")
    
    if bool(getattr(args, "check_contract", False)):
        command.append("--check-contract")

    print("Run explorer memory replay smoke:")
    print(" ".join(command))

    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        check=False,
        text=True,
    )

    return int(completed.returncode or 0)


def run_memory_replay_query(args: argparse.Namespace) -> int:
    """Run explorer-memory evidence replay query and optional contract check."""
    json_output = str(getattr(args, "json_output", "") or "").strip()
    check_contract = bool(getattr(args, "check_contract", False))

    temp_json_path = ""
    if check_contract and not json_output:
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="explorer_memory_replay_query_contract_",
            delete=False,
        )
        temp_json_path = temp_file.name
        temp_file.close()
        json_output = temp_json_path

    command = [
        sys.executable,
        "-m",
        "src.testing.replay_explorer_memory_evidence_query",
        "--db-path",
        str(getattr(args, "db_path", "") or ""),
        "--text-query",
        str(getattr(args, "text_query", "") or ""),
        "--limit",
        str(getattr(args, "limit", 5) or 5),
    ]

    json_input = str(getattr(args, "json_input", "") or "").strip()
    if json_input:
        command.extend(["--json-input", json_input])

    if bool(getattr(args, "json", True)):
        command.append("--json")

    if json_output:
        command.extend(["--json-output", json_output])

    if check_contract:
        command.append("--check-contract")

    print("Run explorer-memory evidence replay query:")
    print(" ".join(command))

    try:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            check=False,
            text=True,
        )

        return int(completed.returncode or 0)

    finally:
        if temp_json_path:
            try:
                Path(temp_json_path).unlink(missing_ok=True)
            except OSError:
                pass

def run_memory_query_hint(args: argparse.Namespace) -> int:
    """Run local memory evidence query and optionally validate its contract."""
    json_output = str(getattr(args, "json_output", "") or "").strip()
    check_contract = bool(getattr(args, "check_contract", False))

    temp_json_path = ""
    if check_contract and not json_output:
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="memory_query_contract_",
            delete=False,
        )
        temp_json_path = temp_file.name
        temp_file.close()
        json_output = temp_json_path

    command = [
        sys.executable,
        "-m",
        "src.testing.query_memory_evidence_catalog",
        "--text-query",
        str(args.text_query),
        "--limit",
        str(args.limit),
    ]

    if bool(getattr(args, "json", True)):
        command.append("--json")

    if json_output:
        command.extend(["--json-output", json_output])

    print("Run local memory evidence catalog query:")
    print(" ".join(command))

    try:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            check=False,
            text=True,
        )

        if completed.returncode != 0:
            return int(completed.returncode or 1)

        if check_contract:
            if not json_output:
                print("❌ memory query contract check requires JSON output")
                return 1

            payload = json.loads(Path(json_output).read_text(encoding="utf-8"))
            assert_memory_evidence_query_contract(payload)
            print("✅ memory evidence query contract OK")

        return 0

    finally:
        if temp_json_path:
            try:
                Path(temp_json_path).unlink(missing_ok=True)
            except OSError:
                pass


def _remove_sqlite_database_files(db_path: str) -> None:
    """Remove SQLite database and sidecar WAL/SHM/lock files for fresh local runs."""
    clean_path = str(db_path or "").strip()
    if not clean_path:
        return

    path = Path(clean_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    for candidate in (
        path,
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
        Path(f"{path}.lock"),
    ):
        try:
            if candidate.exists() and candidate.is_file():
                candidate.unlink()
                print(f"removed SQLite file: {candidate}")
        except OSError as exc:
            raise RuntimeError(f"Failed to remove SQLite file {candidate}: {exc}") from exc
        
def _fresh_runtime_ledgers(run_dir: Path, base_env: Mapping[str, str]) -> None:
    """Remove local runtime SQLite database files for a clean development run."""
    ledger_dir = run_dir / "ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)

    print(f"fresh-crdt requested: run_dir={run_dir}")
    print(f"fresh-crdt requested: ledger_dir={ledger_dir}")
    print(f"fresh-crdt requested: CRDT_DB_PATH={base_env.get('CRDT_DB_PATH')}")
    print(f"fresh-crdt requested: EVENT_SQLITE_PATH={base_env.get('EVENT_SQLITE_PATH')}")

    for key in ("CRDT_DB_PATH", "EVENT_SQLITE_PATH"):
        db_path = str(base_env.get(key, "") or "").strip()
        if db_path:
            if _sqlite_database_is_malformed(db_path):
                _archive_malformed_sqlite_database(db_path, run_dir)
            _remove_sqlite_database_files(db_path)

def _sqlite_database_is_malformed(db_path: str) -> bool:
    """Return True if SQLite database exists but integrity_check cannot read it."""
    import sqlite3

    clean_path = str(db_path or "").strip()
    if not clean_path:
        return False

    path = Path(clean_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        return False
    
    if not _sqlite_file_has_valid_header(str(path)):
        return True

    try:
        with sqlite3.connect(str(path)) as conn:
            row = conn.execute("PRAGMA integrity_check;").fetchone()
            return not row or str(row[0]).lower() != "ok"
    except sqlite3.DatabaseError:
        return True
    except OSError:
        return True
    
def _archive_malformed_sqlite_database(db_path: str, run_dir: Path) -> None:
    """Move malformed SQLite database and sidecars to a quarantine directory."""
    clean_path = str(db_path or "").strip()
    if not clean_path:
        return

    path = Path(clean_path).expanduser().resolve()
    if not path.exists():
        return

    quarantine_dir = run_dir / "corrupt_ledgers"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    for candidate in (
        path,
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    ):
        if candidate.exists() and candidate.is_file():
            target = quarantine_dir / candidate.name
            try:
                candidate.replace(target)
                print(f"archived malformed SQLite file: {candidate} -> {target}")
            except OSError:
                # Fall back to deletion if move fails in dev runtime.
                candidate.unlink(missing_ok=True)
                print(f"removed malformed SQLite file: {candidate}")

def _sqlite_file_has_valid_header(db_path: str) -> bool:
    path = Path(str(db_path or "")).expanduser().resolve()

    if not path.exists() or not path.is_file():
        return True

    if path.stat().st_size == 0:
        return True

    try:
        with path.open("rb") as file:
            return file.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "up":
        raise SystemExit(asyncio.run(run_up(args)))

    if args.command == "status":
        raise SystemExit(run_status(args))

    if args.command == "logs":
        raise SystemExit(run_logs(args))
    
    if args.command == "memory-query":
        raise SystemExit(run_memory_query_hint(args))
    if args.command == "memory-replay-query":
        raise SystemExit(run_memory_replay_query(args))
    
    if args.command == "memory-replay-smoke":
        raise SystemExit(run_memory_replay_smoke(args))
    if args.command == "memory-replay-latest":
        raise SystemExit(run_memory_replay_latest(args))
    
    if args.command == "latest-artifacts":
        raise SystemExit(run_latest_artifacts(args))
    if args.command == "latest-artifacts-cleanup":
        raise SystemExit(run_latest_artifacts_cleanup(args))

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

"""
This module defines FastAPI routes for displaying trade history by parsing Docker container logs.

It provides endpoints to render the trades dashboard page and fetch the latest trade data.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Set, Final

import docker
import docker.errors
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from dashboard.routes.base_template import render_page

logger = logging.getLogger(__name__)
router = APIRouter()

# Regular expressions for extracting swap information from container logs.
SWAP_PATTERNS: Final[List[re.Pattern[str]]] = [
    re.compile(r"INFO:SwarmNode:📡 Real swap result: \{'tx_hash': '(?P<tx_hash>[^']+)', 'status': '(?P<status>[^']+)'\}"),
    re.compile(r'INFO:adapters\.web3_testnet:✅ Swap successful! Tx: (?P<tx_hash>\S+)'),
    re.compile(r'ERROR:adapters\.web3_testnet:❌ Swap (reverted|failed).*Tx: (?P<tx_hash>\S+)'),
]

ATTEMPTING_SWAP_REGEX: Final[re.Pattern[str]] = re.compile(
    r'Attempting real swap.*?(?P<side>buy|sell)\s+(?P<amount>\d+\.?\d*)\s+(?P<symbol>\S+)'
)

LEADER_SWAP_REGEX: Final[re.Pattern[str]] = re.compile(r'Leader, swap: (\S+) (\S+) (\S+)')

def collect_trades(tail: int = 200) -> List[Dict[str, str]]:
    """
    Retrieves and parses trade (swap) information from Docker container logs.

    Args:
        tail: Number of log lines to retrieve per container.

    Returns:
        A list of parsed trades ordered by occurrence, limited to 50 entries.
    """
    trades: List[Dict[str, str]] = []
    try:
        client = docker.from_env()
        containers = client.containers.list(
            filters={"name": "lab_swarm_demo-node", "status": "running"}
        )
    except (docker.errors.DockerException, Exception) as e:
        logger.error("Docker connection error: %s", e)
        return []

    for container in containers:
        container_name_short = container.name.replace("lab_swarm_demo-", "")
        try:
            log_content = container.logs(tail=tail).decode('utf-8', errors='ignore')
        except docker.errors.APIError as e:
            logger.error("Error fetching logs for %s: %s", container.name, e)
            continue

        pending_side: str = 'unknown'
        pending_amount: str = ''
        pending_symbol: str = 'WETH/USDC'

        for line in log_content.splitlines():
            if leader_match := LEADER_SWAP_REGEX.search(line):
                pending_side, pending_amount, pending_symbol = leader_match.groups()
                continue

            if attempting_match := ATTEMPTING_SWAP_REGEX.search(line):
                pending_side = attempting_match.group('side')
                pending_amount = attempting_match.group('amount')
                pending_symbol = attempting_match.group('symbol')
                continue

            tx_hash: Optional[str] = None
            status: Optional[str] = None

            if p0 := SWAP_PATTERNS[0].search(line):
                tx_hash, status = p0.group('tx_hash'), p0.group('status')
            elif p1 := SWAP_PATTERNS[1].search(line):
                tx_hash, status = p1.group('tx_hash'), "success"
            elif p2 := SWAP_PATTERNS[2].search(line):
                tx_hash, status = p2.group('tx_hash'), "failed"

            if tx_hash and status:
                trades.append({
                    "node": container_name_short,
                    "side": pending_side,
                    "amount": pending_amount or '—',
                    "symbol": pending_symbol or 'WETH/USDC',
                    "tx_hash": tx_hash,
                    "status": status,
                })
                pending_side, pending_amount, pending_symbol = 'unknown', '', 'WETH/USDC'

    seen_hashes: Set[str] = set()
    unique_trades: List[Dict[str, str]] = []
    for trade in reversed(trades):
        if trade['tx_hash'] not in seen_hashes:
            seen_hashes.add(trade['tx_hash'])
            unique_trades.append(trade)

    return unique_trades[:50]

TRADES_CONTENT: Final[str] = """
    <section>
        <button class="btn" onclick="fetchTrades()">🔄 Refresh</button>
        <label style="margin-left:1rem; color: #c9d1d9;">
            <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> Auto-refresh (10s)
        </label>
    </section>
    <table id="trades-table">
        <thead>
            <tr><th>Node</th><th>Side</th><th>Amount</th><th>Symbol</th><th>Transaction Hash</th><th>Status</th></tr>
        </thead>
        <tbody></tbody>
    </table>
    <script src="/static/js/trades.js"></script>
"""

@router.get("/trades", response_class=HTMLResponse)
async def trades_page(request: Request) -> HTMLResponse:
    """Renders the trades dashboard page."""
    return HTMLResponse(render_page(request, TRADES_CONTENT, "BlackSwan Trades"))

@router.get("/api/trades")
async def api_trades() -> JSONResponse:
    """API endpoint to fetch the latest trade data."""
    return JSONResponse(content=collect_trades())
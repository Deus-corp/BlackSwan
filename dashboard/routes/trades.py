"""
This module defines FastAPI routes for displaying trade history
by parsing Docker container logs.
"""

import re
from typing import Any, Dict, List, Optional

import docker
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from dashboard.routes.base_template import render_page

router = APIRouter()

# Regular expressions for extracting swap information from container logs.
# These patterns are designed to identify different types of swap result messages.
SWAP_PATTERNS: List[re.Pattern[str]] = [
    # Pattern 0: Matches successful or failed real swap results with tx_hash and status
    re.compile(r"INFO:SwarmNode:📡 Real swap result: \{'tx_hash': '(?P<tx_hash>[^']+)', 'status': '(?P<status>[^']+)'\}"),
    # Pattern 1: Matches successful swap messages with transaction hash
    re.compile(r'INFO:adapters\.web3_testnet:✅ Swap successful! Tx: (?P<tx_hash>\S+)'),
    # Pattern 2: Matches failed or reverted swap messages with transaction hash and reason
    re.compile(r'ERROR:adapters\.web3_testnet:❌ Swap (reverted|failed).*Tx: (?P<tx_hash>\S+)'),
]

def collect_trades(tail: int = 200) -> List[Dict[str, str]]:
    """
    Connects to Docker, retrieves logs from 'lab_swarm_demo-node' containers,
    and parses them to collect recent trade (swap) information.

    The parsing logic attempts to associate a swap initiation (side, amount, symbol)
    with its subsequent transaction result (tx_hash, status).

    Args:
        tail: The number of last log lines to retrieve from each container.

    Returns:
        A list of dictionaries, where each dictionary represents a unique trade.
        Trades are ordered from most recent to oldest, limited to 50 unique entries.
    """
    trades: List[Dict[str, str]] = []
    try:
        client = docker.from_env()
    except docker.errors.DockerException as e:
        print(f"Error connecting to Docker: {e}. Please ensure Docker is running.")
        return []

    containers = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})

    for container in containers:
        try:
            log: str = container.logs(tail=tail).decode('utf-8', errors='ignore')
        except docker.errors.APIError as e:
            print(f"Error fetching logs for container {container.name}: {e}")
            continue

        lines: List[str] = log.splitlines()

        # These variables hold the details of the most recently identified swap *intention*.
        # They are used to populate trade details when a success/failure transaction is found.
        pending_side: str = 'unknown'
        pending_amount: str = ''
        pending_symbol: str = 'WETH/USDC' # Default symbol

        for line in lines:
            # 1. Extract pending swap details from "Leader, swap:" messages
            leader_match: Optional[re.Match[str]] = re.search(r'Leader, swap: (\S+) (\S+) (\S+)', line)
            if leader_match:
                pending_side = leader_match.group(1)
                pending_amount = leader_match.group(2)
                pending_symbol = leader_match.group(3)
                continue

            # 2. Extract pending swap details from older "Attempting real swap" messages
            if 'Attempting real swap' in line:
                # This parsing is less precise, trying to find common patterns.
                # It prioritizes explicit parts and falls back to a generic number match.
                parts: List[str] = line.split()
                if len(parts) >= 5:
                    # Example: "... swap: sell 0.001 WETH/USDC" -> parts[-3] is side, etc.
                    # This might be ambiguous. The original code's logic is preserved.
                    potential_side = parts[-3]
                    potential_amount = parts[-2]
                    potential_symbol = parts[-1]

                    # Basic validation to avoid picking up unrelated strings
                    if potential_side in ['buy', 'sell'] and re.match(r'^\d+(\.\d+)?$', potential_amount):
                        pending_side = potential_side
                        pending_amount = potential_amount
                        pending_symbol = potential_symbol
                    else:
                        # Fallback for amount if direct parsing fails
                        amount_match = re.search(r'(\d+\.?\d*)', line)
                        if amount_match:
                            pending_amount = amount_match.group(1)
                elif not pending_amount: # If amount wasn't set by parts[-2]
                    amount_match = re.search(r'(\d+\.?\d*)', line)
                    if amount_match:
                        pending_amount = amount_match.group(1)
                continue

            # 3. Check for specific swap result patterns defined in SWAP_PATTERNS
            tx_hash: Optional[str] = None
            status: Optional[str] = None

            # Pattern 0: Real swap result with explicit status
            match_p0: Optional[re.Match[str]] = SWAP_PATTERNS[0].search(line)
            if match_p0:
                tx_hash = match_p0.group('tx_hash')
                status = match_p0.group('status')
            else:
                # Pattern 1: Successful swap
                match_p1: Optional[re.Match[str]] = SWAP_PATTERNS[1].search(line)
                if match_p1:
                    tx_hash = match_p1.group('tx_hash')
                    status = "success"
                else:
                    # Pattern 2: Failed/reverted swap
                    match_p2: Optional[re.Match[str]] = SWAP_PATTERNS[2].search(line)
                    if match_p2:
                        tx_hash = match_p2.group('tx_hash')
                        status = "failed"

            if tx_hash and status:
                trades.append({
                    "node": container.name.replace("lab_swarm_demo-", ""),
                    "side": pending_side,
                    "amount": pending_amount if pending_amount else '—',
                    "symbol": pending_symbol if pending_symbol else 'WETH/USDC',
                    "tx_hash": tx_hash,
                    "status": status,
                })
                # Reset pending values, as this transaction is "closed"
                # (though this state management is simplified and assumes 1:1 pairing)
                pending_side = 'unknown'
                pending_amount = ''
                pending_symbol = 'WETH/USDC'
                continue # Move to next line

    # Reverse to get most recent trades first
    trades.reverse()

    # Remove duplicate trades based on transaction hash, keeping the most recent one
    seen_tx_hashes: set[str] = set()
    unique_trades: List[Dict[str, str]] = []
    for trade in trades:
        if trade['tx_hash'] not in seen_tx_hashes:
            seen_tx_hashes.add(trade['tx_hash'])
            unique_trades.append(trade)

    return unique_trades[:50] # Limit to the latest 50 unique trades

# HTML content for the trades page.
# Includes buttons for refresh and auto-refresh toggle, and an empty table
# which will be populated by JavaScript.
TRADES_CONTENT = """
    <section>
        <button class="btn" onclick="fetchTrades()">🔄 Refresh</button>
        <label style="margin-left:1rem; color: #c9d1d9;">
            <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> Auto-refresh (10s)
        </label>
    </section>
    <table id="trades-table">
        <thead>
            <tr>
                <th>Node</th>
                <th>Side</th>
                <th>Amount</th>
                <th>Symbol</th>
                <th>Transaction Hash</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
    <script src="/static/js/trades.js"></script>
"""

@router.get("/trades", response_class=HTMLResponse)
def trades_page(request: Request) -> HTMLResponse:
    """
    Renders the trades dashboard page.

    Args:
        request: The incoming request object.

    Returns:
        An HTMLResponse containing the rendered trades page.
    """
    return HTMLResponse(render_page(request, TRADES_CONTENT, "BlackSwan Trades"))

@router.get("/api/trades")
async def api_trades() -> JSONResponse:
    """
    API endpoint to fetch the latest trade data.

    Returns:
        A JSONResponse containing a list of trade dictionaries.
    """
    trades: List[Dict[str, str]] = collect_trades()
    return JSONResponse(trades)
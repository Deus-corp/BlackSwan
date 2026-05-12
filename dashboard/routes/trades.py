from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from dashboard.routes.base_template import render_page
import docker
import re

router = APIRouter()

# Паттерны для поиска свопов в логах
SWAP_PATTERNS = [
    re.compile(r"INFO:SwarmNode:📡 Real swap result: \{'tx_hash': '([^']+)', 'status': '([^']+)'\}"),
    re.compile(r'INFO:adapters\.web3_testnet:✅ Swap successful! Tx: (\S+)'),
    re.compile(r'ERROR:adapters\.web3_testnet:❌ Swap (reverted|failed).*Tx: (\S+)'),
]

def collect_trades(tail: int = 200) -> list:
    trades = []
    client = docker.from_env()
    containers = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=tail).decode('utf-8', errors='ignore')
        except docker.errors.APIError:
            continue
        lines = log.splitlines()
        pending_side = 'unknown'
        pending_amount = ''
        pending_symbol = ''
        for line in lines:
            if 'Attempting real swap' in line:
                parts = line.split()
                if len(parts) >= 5:
                    pending_side = parts[-3] if len(parts) > 2 else 'unknown'
                    pending_amount = parts[-2] if len(parts) > 1 else ''
                    pending_symbol = parts[-1] if parts else ''
                    # Резервный поиск числа, если не получилось извлечь
                    if not pending_amount:
                        m = re.search(r'(\d+\.?\d*)', line)
                        if m:
                            pending_amount = m.group(1)
            elif '✅ Swap successful!' in line:
                tx_match = re.search(r'Tx: (\S+)', line)
                if tx_match:
                    trades.append({
                        "node": c.name.replace("lab_swarm_demo-", ""),
                        "side": pending_side,
                        "amount": pending_amount,
                        "symbol": pending_symbol,
                        "tx_hash": tx_match.group(1),
                        "status": "success",
                    })
            elif '❌ Swap reverted' in line or '❌ Swap failed' in line:
                tx_match = re.search(r'Tx: (\S+)', line)
                if tx_match:
                    trades.append({
                        "node": c.name.replace("lab_swarm_demo-", ""),
                        "side": pending_side,
                        "amount": pending_amount,
                        "symbol": pending_symbol,
                        "tx_hash": tx_match.group(1),
                        "status": "failed",
                    })
    trades.reverse()
    # Убираем дубли по tx_hash
    seen = set()
    unique_trades = []
    for t in trades:
        if t['tx_hash'] not in seen:
            seen.add(t['tx_hash'])
            unique_trades.append(t)
    return unique_trades[:50]


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
def trades_page(request: Request):
    return HTMLResponse(render_page(request, TRADES_CONTENT, "BlackSwan Trades"))

@router.get("/api/trades")
def api_trades():
    trades = collect_trades()
    return JSONResponse(trades)
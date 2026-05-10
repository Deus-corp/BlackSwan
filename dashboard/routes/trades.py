from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
import docker
import re
from datetime import datetime

router = APIRouter()

# Паттерны для поиска свопов в логах
SWAP_PATTERNS = [
    re.compile(r'INFO:SwarmNode:📡 Real swap result: \{\'tx_hash\': \'([^\']+)\', \'status\': \'([^\']+)\'\}'),
    re.compile(r'INFO:adapters\.web3_testnet:✅ Swap successful! Tx: (\S+)'),
    re.compile(r'ERROR:adapters\.web3_testnet:❌ Swap (reverted|failed).*Tx: (\S+)'),
]

def collect_trades(tail: int = 500) -> list:
    trades = []
    client = docker.from_env()
    containers = client.containers.list(filters={"name": "lab_swarm_demo-node", "status": "running"})
    for c in containers:
        try:
            log = c.logs(tail=tail).decode('utf-8', errors='ignore')
        except docker.errors.APIError:
            continue
        lines = log.splitlines()
        for line in lines:
            # Извлекаем side и amount
            side_match = re.search(r'Attempting real swap: (\w+) ([\d.]+) (\S+)', line)
            side = side_match.group(1) if side_match else 'unknown'
            amount = side_match.group(2) if side_match else ''
            symbol = side_match.group(3) if side_match else ''

            # Ищем tx_hash и статус
            tx_hash = None
            status = None
            m = re.search(r"'tx_hash': '([^']+)'.*'status': '([^']+)'", line)
            if m:
                tx_hash = m.group(1)
                status = m.group(2)
            else:
                m = re.search(r'✅ Swap successful! Tx: (\S+)', line)
                if m:
                    tx_hash = m.group(1)
                    status = 'success'
                else:
                    m = re.search(r'❌ Swap (reverted|failed).*Tx: (\S+)', line)
                    if m:
                        tx_hash = m.group(2)
                        status = 'failed'
            if tx_hash:
                trades.append({
                    "node": c.name.replace("lab_swarm_demo-", ""),
                    "side": side,
                    "amount": amount,
                    "symbol": symbol,
                    "tx_hash": tx_hash,
                    "status": status,
                })
    trades.reverse()
    return trades[:50]

TRADES_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BlackSwan Trades</title>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <h1>🦢 Trade Feed</h1>
    <div class="tabs">
        <a href="/">🏠 Main</a>
        <a href="/trades" class="active">📈 Trades</a>
        <a href="/logs">📜 Logs</a>
        <a href="/dashboard">📊 Dashboard</a>
        <a href="/settings">⚙️ Settings</a>
    </div>
    <section>
        <button class="btn" onclick="fetchTrades()">🔄 Refresh</button>
        <label style="margin-left:1rem; color: #c9d1d9;">
            <input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> Auto-refresh (10s)
        </label>
    </section>
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

    <script src="/static/js/trades.js"></script>
</body>
</html>
"""

@router.get("/trades", response_class=HTMLResponse)
def trades_page():
    return HTMLResponse(TRADES_HTML)

@router.get("/api/trades")
def api_trades():
    trades = collect_trades()
    return JSONResponse(trades)
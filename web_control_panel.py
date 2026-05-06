#!/usr/bin/env python3
"""
BlackSwan Web Control Panel – полное управление роем через браузер.
Запуск: python3 web_control_panel.py (откроется на http://localhost:8080)
"""
import subprocess
import time
from pathlib import Path
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = PROJECT_ROOT / "mvp" / "lab_swarm_demo" / "docker-compose.async.yml"

app = FastAPI(title="BlackSwan Control Panel")

HTML_HEADER = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BlackSwan Control Panel</title>
    <style>
        body { font-family: sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #1a1a2e; color: #e0e0e0; }
        h1 { color: #f0c000; }
        section { background: #16213e; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
        button, input[type=submit] { background: #e94560; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; cursor: pointer; font-size: 1rem; margin-right: 0.5rem; }
        button:hover { background: #c23152; }
        input[type=text], select { padding: 0.5rem; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: white; margin-right: 0.5rem; }
        pre { background: #0d1117; padding: 1rem; border-radius: 8px; overflow-x: auto; max-height: 400px; }
        .row { display: flex; align-items: center; margin-bottom: 0.5rem; }
        .row label { width: 300px; }
    </style>
</head>
<body>
    <h1>🦢 BlackSwan Control Panel</h1>
"""

HTML_FOOTER = """</body>
</html>"""

def render_page(message: str = "") -> str:
    """Собирает HTML-страницу с переданным сообщением."""
    msg_section = ""
    if message:
        msg_section = f"""<section><h3>Result</h3><pre>{message}</pre></section>"""
    
    return f"""{HTML_HEADER}
    <section>
        <h2>Swarm Actions</h2>
        <form action="/api/start" method="post" style="display:inline">
            <button type="submit">🚀 Start (4 nodes)</button>
        </form>
        <form action="/api/stop" method="post" style="display:inline">
            <button type="submit">⏹️ Stop</button>
        </form>
        <form action="/api/rebuild" method="post" style="display:inline">
            <button type="submit">🔄 Rebuild & Start</button>
        </form>
    </section>
    <section>
        <h2>Monitoring</h2>
        <form action="/api/logs" method="get" style="display:inline">
            <button type="submit">📜 Show Last Logs</button>
        </form>
        <form action="/api/save_logs" method="post" style="display:inline">
            <button type="submit">💾 Save Logs to File</button>
        </form>
    </section>
    <section>
        <h2>Configuration</h2>
        <form action="/api/update_config" method="post">
            <div class="row"><label>LLM_MODEL</label><select name="LLM_MODEL"><option>deepseek</option><option>smollm17</option></select></div>
            <div class="row"><label>BURN_RATE</label><input type="text" name="BURN_RATE" value="0.2"></div>
            <div class="row"><label>FAILURE_PROB</label><input type="text" name="FAILURE_PROB" value="0.0"></div>
            <div class="row"><label>TOTAL_NODES</label><input type="text" name="TOTAL_NODES" value="4"></div>
            <div class="row"><label>GOSSIP_SIGNING_ENABLED</label><select name="GOSSIP_SIGNING_ENABLED"><option>false</option><option>true</option></select></div>
            <div class="row"><label>MEMORY_API_ENABLED</label><select name="MEMORY_API_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>MARKET_MODE</label><select name="MARKET_MODE"><option>sim</option><option>live</option><option>futures</option><option>web3</option></select></div>
            <div class="row"><label>FUTURES_LEVERAGE</label><input type="text" name="FUTURES_LEVERAGE" value="2"></div>
            <div class="row"><label>STOP_LOSS_PERCENT</label><input type="text" name="STOP_LOSS_PERCENT" value="2.0"></div>
            <div class="row"><label>MAX_LEVERAGE</label><input type="text" name="MAX_LEVERAGE" value="5"></div>
            <div class="row"><label>MIN_LEVERAGE</label><input type="text" name="MIN_LEVERAGE" value="1"></div>
            <div class="row"><label>PRICE_SCALE</label><input type="text" name="PRICE_SCALE" value="10000"></div>
            <div class="row"><label>TRADING_SYMBOLS</label><input type="text" name="TRADING_SYMBOLS" value="BTC/USDT,ETH/USDT,SOL/USDT"></div>
            <div class="row"><label>INTERNET_RESEARCHER_ENABLED</label><select name="INTERNET_RESEARCHER_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>TRADINGVIEW_WEBHOOK_ENABLED</label><select name="TRADINGVIEW_WEBHOOK_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>TRADINGVIEW_WEBHOOK_PORT</label><input type="text" name="TRADINGVIEW_WEBHOOK_PORT" value="8888"></div>
            <div class="row"><label>ORDERBOOK_ANALYSIS_ENABLED</label><select name="ORDERBOOK_ANALYSIS_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>HEDGE_ENABLED</label><select name="HEDGE_ENABLED"><option>false</option><option>true</option></select></div>
            <div class="row"><label>HEDGE_RATIO</label><input type="text" name="HEDGE_RATIO" value="0.5"></div>
            <button type="submit">💾 Save & Restart</button>
        </form>
    </section>
    {msg_section}
    {HTML_FOOTER}"""

@app.get("/", response_class=HTMLResponse)
def index():
    return render_page()

@app.post("/api/start")
async def start_swarm():
    result = subprocess.run(f"docker compose -f {COMPOSE_FILE} up -d --scale node=4", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    return render_page(result.stdout or result.stderr)

@app.post("/api/stop")
async def stop_swarm():
    result = subprocess.run(f"docker compose -f {COMPOSE_FILE} down", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    return render_page(result.stdout or result.stderr)

@app.post("/api/rebuild")
async def rebuild_swarm():
    stop = subprocess.run(f"docker compose -f {COMPOSE_FILE} down", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    build = subprocess.run(f"docker compose -f {COMPOSE_FILE} build --no-cache", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    start = subprocess.run(f"docker compose -f {COMPOSE_FILE} up -d --scale node=4", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    msg = f"STOP:\n{stop.stdout}\nBUILD:\n{build.stdout}\nSTART:\n{start.stdout}"
    return render_page(msg)

@app.get("/api/logs", response_class=HTMLResponse)
async def show_logs():
    result = subprocess.run(f"docker compose -f {COMPOSE_FILE} logs --tail 50", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    return render_page(result.stdout or result.stderr)

@app.post("/api/save_logs", response_class=HTMLResponse)
async def save_logs():
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    dest_dir = PROJECT_ROOT / "logs" / f"swarm_logs_{timestamp}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, 5):
        log = subprocess.run(f"docker logs lab_swarm_demo-node-{i} 2>&1", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
        (dest_dir / f"node-{i}.log").write_text(log.stdout)
    combined = subprocess.run(f"docker compose -f {COMPOSE_FILE} logs --no-color 2>&1", shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
    (dest_dir / "all_nodes.log").write_text(combined.stdout)
    return render_page(f"Logs saved to {dest_dir}")

@app.post("/api/update_config")
async def update_config(
    LLM_MODEL: str = Form(...),
    BURN_RATE: str = Form(...),
    FAILURE_PROB: str = Form(...),
    TOTAL_NODES: str = Form(...),
    GOSSIP_SIGNING_ENABLED: str = Form(...),
    MEMORY_API_ENABLED: str = Form(...),
    MARKET_MODE: str = Form(...),
    FUTURES_LEVERAGE: str = Form(...),
    STOP_LOSS_PERCENT: str = Form(...),
    MAX_LEVERAGE: str = Form(...),
    MIN_LEVERAGE: str = Form(...),
    PRICE_SCALE: str = Form(...),
    TRADING_SYMBOLS: str = Form(...),
    INTERNET_RESEARCHER_ENABLED: str = Form(...),
    TRADINGVIEW_WEBHOOK_ENABLED: str = Form(...),
    TRADINGVIEW_WEBHOOK_PORT: str = Form(...),
    ORDERBOOK_ANALYSIS_ENABLED: str = Form(...),
    HEDGE_ENABLED: str = Form(...),
    HEDGE_RATIO: str = Form(...),
):
    content = COMPOSE_FILE.read_text()
    replacements = {
        "LLM_MODEL=": f"LLM_MODEL={LLM_MODEL}",
        "BURN_RATE=": f"BURN_RATE={BURN_RATE}",
        "FAILURE_PROB=": f"FAILURE_PROB={FAILURE_PROB}",
        "TOTAL_NODES=": f"TOTAL_NODES={TOTAL_NODES}",
        "GOSSIP_SIGNING_ENABLED=": f"GOSSIP_SIGNING_ENABLED={GOSSIP_SIGNING_ENABLED}",
        "MEMORY_API_ENABLED=": f"MEMORY_API_ENABLED={MEMORY_API_ENABLED}",
        "MARKET_MODE=": f"MARKET_MODE={MARKET_MODE}",
        "FUTURES_LEVERAGE=": f"FUTURES_LEVERAGE={FUTURES_LEVERAGE}",
        "STOP_LOSS_PERCENT=": f"STOP_LOSS_PERCENT={STOP_LOSS_PERCENT}",
        "MAX_LEVERAGE=": f"MAX_LEVERAGE={MAX_LEVERAGE}",
        "MIN_LEVERAGE=": f"MIN_LEVERAGE={MIN_LEVERAGE}",
        "PRICE_SCALE=": f"PRICE_SCALE={PRICE_SCALE}",
        "TRADING_SYMBOLS=": f"TRADING_SYMBOLS={TRADING_SYMBOLS}",
        "INTERNET_RESEARCHER_ENABLED=": f"INTERNET_RESEARCHER_ENABLED={INTERNET_RESEARCHER_ENABLED}",
        "TRADINGVIEW_WEBHOOK_ENABLED=": f"TRADINGVIEW_WEBHOOK_ENABLED={TRADINGVIEW_WEBHOOK_ENABLED}",
        "TRADINGVIEW_WEBHOOK_PORT=": f"TRADINGVIEW_WEBHOOK_PORT={TRADINGVIEW_WEBHOOK_PORT}",
        "ORDERBOOK_ANALYSIS_ENABLED=": f"ORDERBOOK_ANALYSIS_ENABLED={ORDERBOOK_ANALYSIS_ENABLED}",
        "HEDGE_ENABLED=": f"HEDGE_ENABLED={HEDGE_ENABLED}",
        "HEDGE_RATIO=": f"HEDGE_RATIO={HEDGE_RATIO}",
    }
    for old_prefix, new_line in replacements.items():
        content = content.replace(old_prefix, f"#{old_prefix}")
        content = content.replace(f"#{old_prefix}", new_line, 1)
    COMPOSE_FILE.write_text(content)
    subprocess.run(f"docker compose -f {COMPOSE_FILE} down", shell=True, capture_output=True, cwd=PROJECT_ROOT)
    subprocess.run(f"docker compose -f {COMPOSE_FILE} up -d --scale node=4", shell=True, capture_output=True, cwd=PROJECT_ROOT)
    return render_page("Configuration saved and swarm restarted.")

if __name__ == "__main__":
    print("🌐 Панель управления запущена на http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
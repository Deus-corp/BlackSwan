#!/usr/bin/env python3
"""
BlackSwan Web Control Panel – управление роем через браузер.
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

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BlackSwan Control Panel</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; background: #1a1a2e; color: #e0e0e0; }
        h1 { color: #f0c000; }
        section { background: #16213e; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
        button, input[type=submit] { background: #e94560; color: white; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; cursor: pointer; font-size: 1rem; margin-right: 0.5rem; }
        button:hover { background: #c23152; }
        input[type=text], select { padding: 0.5rem; border-radius: 8px; border: 1px solid #30363d; background: #0d1117; color: white; margin-right: 0.5rem; }
        pre { background: #0d1117; padding: 1rem; border-radius: 8px; overflow-x: auto; max-height: 300px; }
    </style>
</head>
<body>
    <h1>🦢 BlackSwan Control Panel</h1>
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
        <h2>Configuration</h2>
        <form action="/api/change_model" method="post">
            <label>LLM Model:</label>
            <select name="model">
                <option value="deepseek">deepseek</option>
                <option value="qwen">qwen</option>
                <option value="smollm2">smollm2</option>
                <option value="smollm17">smollm17</option>
                <option value="llama1b">llama1b</option>
                <option value="unc_llama1b">unc_llama1b</option>
            </select>
            <button type="submit">Apply</button>
        </form>
        <br>
        <form action="/api/change_market" method="post">
            <label>Market Mode:</label>
            <select name="mode">
                <option value="sim">sim</option>
                <option value="live">live</option>
                <option value="web3">web3</option>
            </select>
            <button type="submit">Apply</button>
        </form>
    </section>
    <section>
        <h2>Monitoring</h2>
        <form action="/api/logs" method="get">
            <button type="submit">📜 Show Last Logs</button>
        </form>
        <br>
        <form action="/api/save_logs" method="post">
            <button type="submit">💾 Save Logs to File</button>
        </form>
    </section>
    {% if message %}
    <section>
        <h3>Result</h3>
        <pre>{{ message }}</pre>
    </section>
    {% endif %}
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index(message: str = ""):
    return HTML_TEMPLATE.replace("{% if message %}", "").replace("{% endif %}", "").replace("{{ message }}", message)

@app.post("/api/start")
async def start_swarm():
    result = subprocess.run(
        f"docker compose -f {COMPOSE_FILE} up -d --scale node=4",
        shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return HTML_TEMPLATE.replace("{{ message }}", result.stdout or result.stderr)

@app.post("/api/stop")
async def stop_swarm():
    result = subprocess.run(
        f"docker compose -f {COMPOSE_FILE} down",
        shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return HTML_TEMPLATE.replace("{{ message }}", result.stdout or result.stderr)

@app.post("/api/rebuild")
async def rebuild_swarm():
    stop = subprocess.run(
        f"docker compose -f {COMPOSE_FILE} down",
        shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    build = subprocess.run(
        f"docker compose -f {COMPOSE_FILE} build --no-cache",
        shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    start = subprocess.run(
        f"docker compose -f {COMPOSE_FILE} up -d --scale node=4",
        shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    msg = f"STOP:\n{stop.stdout}\nBUILD:\n{build.stdout}\nSTART:\n{start.stdout}"
    return HTML_TEMPLATE.replace("{{ message }}", msg)

@app.post("/api/change_model")
async def change_model(model: str = Form(...)):
    content = COMPOSE_FILE.read_text()
    new_content = content.replace("LLM_MODEL=", "#LLM_MODEL=")
    new_content = new_content.replace("#LLM_MODEL=", f"LLM_MODEL={model}", 1)
    COMPOSE_FILE.write_text(new_content)
    return HTML_TEMPLATE.replace("{{ message }}", f"Model changed to {model}. Restart swarm to apply.")

@app.post("/api/change_market")
async def change_market(mode: str = Form(...)):
    content = COMPOSE_FILE.read_text()
    new_content = content.replace("MARKET_MODE=", "#MARKET_MODE=")
    new_content = new_content.replace("#MARKET_MODE=", f"MARKET_MODE={mode}", 1)
    COMPOSE_FILE.write_text(new_content)
    return HTML_TEMPLATE.replace("{{ message }}", f"Market mode changed to {mode}. Restart swarm to apply.")

@app.get("/api/logs")
async def show_logs():
    result = subprocess.run(
        f"docker compose -f {COMPOSE_FILE} logs --tail 30",
        shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return HTML_TEMPLATE.replace("{{ message }}", result.stdout or result.stderr)

@app.post("/api/save_logs")
async def save_logs():
    dest = PROJECT_ROOT / "docs" / "logs" / f"swarm_logs_{int(time.time())}.log"
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        f"docker compose -f {COMPOSE_FILE} logs --no-color > {dest}",
        shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT
    )
    return HTML_TEMPLATE.replace("{{ message }}", f"Logs saved to {dest}")

if __name__ == "__main__":
    print("🌐 Панель управления запущена на http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
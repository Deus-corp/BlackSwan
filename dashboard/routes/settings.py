from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from dashboard.docker_service import update_config
from dashboard.routes.base_template import render_page
from pathlib import Path
import subprocess

router = APIRouter()

SETTINGS_CONTENT = """
    <section>
        <h2>Compose Configuration</h2>
        <form action="/api/update_config" method="post">
            <div class="row"><label>BURN_RATE</label><input type="text" name="BURN_RATE" value="0.0"></div>
            <div class="row"><label>FAILURE_PROB</label><input type="text" name="FAILURE_PROB" value="0.0"></div>
            <div class="row"><label>GOSSIP_PORT</label><input type="text" name="GOSSIP_PORT" value="9777"></div>
            <div class="row"><label>TOTAL_NODES</label><input type="text" name="TOTAL_NODES" value="4"></div>
            <div class="row"><label>PYTHONUNBUFFERED</label><input type="text" name="PYTHONUNBUFFERED" value="1"></div>
            <div class="row"><label>LLM_MODEL</label><select name="LLM_MODEL"><option>deepseek</option><option>smollm17</option></select></div>
            <div class="row"><label>GOSSIP_SIGNING_ENABLED</label><select name="GOSSIP_SIGNING_ENABLED"><option>false</option><option>true</option></select></div>
            <div class="row"><label>MEMORY_API_ENABLED</label><select name="MEMORY_API_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>MARKET_MODE</label><select name="MARKET_MODE"><option>web3</option><option>sim</option><option>futures</option></select></div>
            <div class="row"><label>TEST_WEB3_SWAP_AMOUNT</label><input type="text" name="TEST_WEB3_SWAP_AMOUNT" value="0.001"></div>
            <div class="row"><label>TEST_WEB3_SWAP_SIDE</label><select name="TEST_WEB3_SWAP_SIDE"><option>sell</option><option>buy</option></select></div>
            <div class="row"><label>WEB3_POOL_FEE</label><input type="text" name="WEB3_POOL_FEE" value="3000"></div>
            <div class="row"><label>PRICE_SCALE</label><input type="text" name="PRICE_SCALE" value="10000"></div>
            <div class="row"><label>MIN_WETH_BALANCE</label><input type="text" name="MIN_WETH_BALANCE" value="0.001"></div>
            <div class="row"><label>MIN_ETH_BALANCE</label><input type="text" name="MIN_ETH_BALANCE" value="0.002"></div>
            <div class="row"><label>MAX_USDC_BALANCE</label><input type="text" name="MAX_USDC_BALANCE" value="500"></div>
            <div class="row"><label>TRADING_SYMBOLS</label><input type="text" name="TRADING_SYMBOLS" value="WETH/USDC"></div>
            <div class="row"><label>LOG_LEVEL</label><select name="LOG_LEVEL"><option>INFO</option><option>DEBUG</option></select></div>
            <div class="row"><label>INTERNET_RESEARCHER_ENABLED</label><select name="INTERNET_RESEARCHER_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>TRADINGVIEW_WEBHOOK_ENABLED</label><select name="TRADINGVIEW_WEBHOOK_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>TRADINGVIEW_WEBHOOK_PORT</label><input type="text" name="TRADINGVIEW_WEBHOOK_PORT" value="8888"></div>
            <div class="row"><label>ORDERBOOK_ANALYSIS_ENABLED</label><select name="ORDERBOOK_ANALYSIS_ENABLED"><option>false</option><option>true</option></select></div>
            <div class="row"><label>HEDGE_ENABLED</label><select name="HEDGE_ENABLED"><option>true</option><option>false</option></select></div>
            <div class="row"><label>HEDGE_RATIO</label><input type="text" name="HEDGE_RATIO" value="0.5"></div>
            <div class="row"><label>CAPITAL_ALERT_THRESHOLD</label><input type="text" name="CAPITAL_ALERT_THRESHOLD" value="100.0"></div>
            <button type="submit">💾 Save & Restart</button>
        </form>
    </section>
    <section>
        <h2>Secrets (.env)</h2>
        <form action="/api/update_secrets" method="post">
            <div class="row"><label>WEB3_PRIVATE_KEY</label><input type="password" name="WEB3_PRIVATE_KEY" placeholder="0x..."></div>
            <div class="row"><label>BINANCE_TESTNET_API_KEY</label><input type="password" name="BINANCE_TESTNET_API_KEY"></div>
            <div class="row"><label>BINANCE_TESTNET_API_SECRET</label><input type="password" name="BINANCE_TESTNET_API_SECRET"></div>
            <div class="row"><label>TELEGRAM_BOT_TOKEN</label><input type="password" name="TELEGRAM_BOT_TOKEN"></div>
            <div class="row"><label>TELEGRAM_CHAT_ID</label><input type="text" name="TELEGRAM_CHAT_ID"></div>
            <div class="row"><label>ETHERSCAN_API_KEY</label><input type="password" name="ETHERSCAN_API_KEY"></div>
            <div class="row"><label>WEB3_RPC_URL</label><input type="text" name="WEB3_RPC_URL" placeholder="https://..."></div>
            <button type="submit">💾 Update Secrets</button>
        </form>
    </section>
    <section>
        <h2>Token Approval</h2>
        <button onclick="approve('WETH')">Approve WETH</button>
        <button onclick="approve('USDC')">Approve USDC</button>
        <span id="approve-msg"></span>
    </section>
    <script>
        async function approve(token) {
            const res = await fetch(`/api/approve/${token}`, { method: 'POST' });
            const text = await res.text();
            document.getElementById('approve-msg').textContent = text;
        }
    </script>
"""

@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return HTMLResponse(render_page(request, SETTINGS_CONTENT, "Settings"))

@router.post("/api/update_config")
async def update_config_form(
    BURN_RATE: str = Form(...),
    FAILURE_PROB: str = Form(...),
    GOSSIP_PORT: str = Form(...),
    TOTAL_NODES: str = Form(...),
    PYTHONUNBUFFERED: str = Form(...),
    LLM_MODEL: str = Form(...),
    GOSSIP_SIGNING_ENABLED: str = Form(...),
    MEMORY_API_ENABLED: str = Form(...),
    MARKET_MODE: str = Form(...),
    TEST_WEB3_SWAP_AMOUNT: str = Form(...),
    TEST_WEB3_SWAP_SIDE: str = Form(...),
    WEB3_POOL_FEE: str = Form(...),
    PRICE_SCALE: str = Form(...),
    MIN_WETH_BALANCE: str = Form(...),
    MIN_ETH_BALANCE: str = Form(...),
    MAX_USDC_BALANCE: str = Form(...),
    TRADING_SYMBOLS: str = Form(...),
    LOG_LEVEL: str = Form(...),
    INTERNET_RESEARCHER_ENABLED: str = Form(...),
    TRADINGVIEW_WEBHOOK_ENABLED: str = Form(...),
    TRADINGVIEW_WEBHOOK_PORT: str = Form(...),
    ORDERBOOK_ANALYSIS_ENABLED: str = Form(...),
    HEDGE_ENABLED: str = Form(...),
    HEDGE_RATIO: str = Form(...),
    CAPITAL_ALERT_THRESHOLD: str = Form(...),
):
    config = {k: v for k, v in locals().items() if k != 'self'}
    msg = update_config(config)
    return HTMLResponse(f"<pre>{msg}</pre>")

@router.post("/api/update_secrets")
async def update_secrets(
    WEB3_PRIVATE_KEY: str = Form(""),
    BINANCE_TESTNET_API_KEY: str = Form(""),
    BINANCE_TESTNET_API_SECRET: str = Form(""),
    TELEGRAM_BOT_TOKEN: str = Form(""),
    TELEGRAM_CHAT_ID: str = Form(""),
    ETHERSCAN_API_KEY: str = Form(""),
    WEB3_RPC_URL: str = Form(""),
):
    env_path = Path(__file__).resolve().parent.parent.parent / "mvp" / "lab_swarm_demo" / ".env"
    lines = env_path.read_text().splitlines()
    updated_keys = set()
    secret_map = {
        "WEB3_PRIVATE_KEY": WEB3_PRIVATE_KEY,
        "BINANCE_TESTNET_API_KEY": BINANCE_TESTNET_API_KEY,
        "BINANCE_TESTNET_API_SECRET": BINANCE_TESTNET_API_SECRET,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "ETHERSCAN_API_KEY": ETHERSCAN_API_KEY,
        "WEB3_RPC_URL": WEB3_RPC_URL,
    }
    new_lines = []
    for line in lines:
        replaced = False
        for key, value in secret_map.items():
            if line.startswith(key + "="):
                new_lines.append(f"{key}={value}")
                updated_keys.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)
    for key, value in secret_map.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n")
    return HTMLResponse("<pre>Secrets updated. Restart swarm to apply.</pre>")

@router.post("/api/approve/{token}")
async def approve_token(token: str):
    project_root = Path(__file__).resolve().parent.parent.parent
    if token.upper() == "WETH":
        cmd = f"python tools/approve_weth.py"
    else:
        cmd = f"python tools/approve_usdc.py"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=project_root)
    return HTMLResponse(f"<pre>{result.stdout or result.stderr}</pre>")
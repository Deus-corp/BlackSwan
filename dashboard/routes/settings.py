"""
This module defines FastAPI routes for the dashboard settings page,
allowing users to configure Docker Compose environment variables (config),
update secret environment variables (.env file), and initiate token approval processes.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from dashboard.docker_service import update_config
from dashboard.routes.base_template import render_page

router = APIRouter()

# HTML content for the settings page.
# It includes forms for Docker Compose configuration and .env secrets,
# and buttons for token approval.
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
def settings_page(request: Request) -> HTMLResponse:
    """
    Renders the settings page with configuration forms and token approval options.

    Args:
        request: The incoming request object.

    Returns:
        An HTMLResponse containing the rendered settings page.
    """
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
) -> HTMLResponse:
    """
    Handles the submission of the Docker Compose configuration form.
    It collects all form fields and passes them to the `update_config` service.

    Args:
        BURN_RATE, FAILURE_PROB, etc.: Individual form fields,
                                       typed as string as received from HTML form.

    Returns:
        An HTMLResponse containing a message about the update status.
    """
    # Collects all form parameters into a dictionary.
    # This approach relies on `locals()` containing only the function parameters
    # at this point. For more robust data handling, a Pydantic model would be
    # preferred in a larger application.
    config: Dict[str, str] = {k: v for k, v in locals().items() if k not in ['self', 'update_config_form', 'Form']}
    msg: str = update_config(config)
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
) -> HTMLResponse:
    """
    Handles the submission of the secrets form, updating the .env file.
    It reads the existing .env file, updates or adds the provided secret keys,
    and writes the changes back.

    Args:
        WEB3_PRIVATE_KEY, BINANCE_TESTNET_API_KEY, etc.: Secret form fields.
                                                           Default to empty string if not provided.

    Returns:
        An HTMLResponse indicating that secrets have been updated and a restart is needed.
    """
    # Determine the path to the .env file relative to the current script.
    # This path is hardcoded and assumes a specific project structure.
    # In a production environment, this path might be better configured
    # via environment variables or a more dynamic lookup.
    project_root = Path(__file__).resolve().parent.parent.parent
    env_path: Path = project_root / "mvp" / "lab_swarm_demo" / ".env"

    current_lines: list[str] = []
    if env_path.exists():
        current_lines = env_path.read_text().splitlines()

    updated_keys: set[str] = set()
    secret_map: Dict[str, str] = {
        "WEB3_PRIVATE_KEY": WEB3_PRIVATE_KEY,
        "BINANCE_TESTNET_API_KEY": BINANCE_TESTNET_API_KEY,
        "BINANCE_TESTNET_API_SECRET": BINANCE_TESTNET_API_SECRET,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "ETHERSCAN_API_KEY": ETHERSCAN_API_KEY,
        "WEB3_RPC_URL": WEB3_RPC_URL,
    }

    new_lines: list[str] = []
    for line in current_lines:
        replaced = False
        # Check if the line starts with any of the secret keys from the form
        for key, value in secret_map.items():
            # Basic check, does not handle commented lines or quoted values correctly
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                updated_keys.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)

    # Append any keys that were in the form but not found in the original .env file
    for key, value in secret_map.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    # Write the updated content back to the .env file, ensuring a trailing newline
    env_path.write_text("\n".join(new_lines) + "\n")
    return HTMLResponse("<pre>Secrets updated. Restart swarm to apply.</pre>")

@router.post("/api/approve/{token}")
async def approve_token(token: str) -> HTMLResponse:
    """
    Initiates a token approval script for WETH or USDC.

    Args:
        token: The token symbol (e.g., 'WETH', 'USDC') to approve.

    Returns:
        An HTMLResponse containing the standard output or error from the approval script.
    """
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    command: list[str]
    if token.upper() == "WETH":
        command = ["python", "tools/approve_weth.py"]
    elif token.upper() == "USDC":
        command = ["python", "tools/approve_usdc.py"]
    else:
        return HTMLResponse(f"<pre>Error: Unknown token '{token}'</pre>", status_code=400)

    # Execute the approval script. Using a list for `cmd` and `shell=False` is safer.
    result: subprocess.CompletedProcess = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=project_root,
        check=False  # Do not raise an exception for non-zero exit codes
    )
    # Return the stdout or stderr from the script execution
    return HTMLResponse(f"<pre>{result.stdout or result.stderr}</pre>")
"""
This module defines FastAPI routes for the dashboard settings page,
allowing users to configure Docker Compose environment variables (config),
update secret environment variables (.env file), and initiate token approval processes.
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

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
async def settings_page(request: Request) -> HTMLResponse:
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
    burn_rate: str = Form(..., alias="BURN_RATE"),
    failure_prob: str = Form(..., alias="FAILURE_PROB"),
    gossip_port: str = Form(..., alias="GOSSIP_PORT"),
    total_nodes: str = Form(..., alias="TOTAL_NODES"),
    pythonunbuffered: str = Form(..., alias="PYTHONUNBUFFERED"),
    llm_model: str = Form(..., alias="LLM_MODEL"),
    gossip_signing_enabled: str = Form(..., alias="GOSSIP_SIGNING_ENABLED"),
    memory_api_enabled: str = Form(..., alias="MEMORY_API_ENABLED"),
    market_mode: str = Form(..., alias="MARKET_MODE"),
    test_web3_swap_amount: str = Form(..., alias="TEST_WEB3_SWAP_AMOUNT"),
    test_web3_swap_side: str = Form(..., alias="TEST_WEB3_SWAP_SIDE"),
    web3_pool_fee: str = Form(..., alias="WEB3_POOL_FEE"),
    price_scale: str = Form(..., alias="PRICE_SCALE"),
    min_weth_balance: str = Form(..., alias="MIN_WETH_BALANCE"),
    min_eth_balance: str = Form(..., alias="MIN_ETH_BALANCE"),
    max_usdc_balance: str = Form(..., alias="MAX_USDC_BALANCE"),
    trading_symbols: str = Form(..., alias="TRADING_SYMBOLS"),
    log_level: str = Form(..., alias="LOG_LEVEL"),
    internet_researcher_enabled: str = Form(..., alias="INTERNET_RESEARCHER_ENABLED"),
    tradingview_webhook_enabled: str = Form(..., alias="TRADINGVIEW_WEBHOOK_ENABLED"),
    tradingview_webhook_port: str = Form(..., alias="TRADINGVIEW_WEBHOOK_PORT"),
    orderbook_analysis_enabled: str = Form(..., alias="ORDERBOOK_ANALYSIS_ENABLED"),
    hedge_enabled: str = Form(..., alias="HEDGE_ENABLED"),
    hedge_ratio: str = Form(..., alias="HEDGE_RATIO"),
    capital_alert_threshold: str = Form(..., alias="CAPITAL_ALERT_THRESHOLD"),
) -> HTMLResponse:
    """
    Handles the submission of the Docker Compose configuration form.
    It collects all form fields and passes them to the `update_config` service.

    Args:
        burn_rate (str): The value for BURN_RATE.
        failure_prob (str): The value for FAILURE_PROB.
        gossip_port (str): The value for GOSSIP_PORT.
        total_nodes (str): The value for TOTAL_NODES.
        pythonunbuffered (str): The value for PYTHONUNBUFFERED.
        llm_model (str): The value for LLM_MODEL.
        gossip_signing_enabled (str): The value for GOSSIP_SIGNING_ENABLED.
        memory_api_enabled (str): The value for MEMORY_API_ENABLED.
        market_mode (str): The value for MARKET_MODE.
        test_web3_swap_amount (str): The value for TEST_WEB3_SWAP_AMOUNT.
        test_web3_swap_side (str): The value for TEST_WEB3_SWAP_SIDE.
        web3_pool_fee (str): The value for WEB3_POOL_FEE.
        price_scale (str): The value for PRICE_SCALE.
        min_weth_balance (str): The value for MIN_WETH_BALANCE.
        min_eth_balance (str): The value for MIN_ETH_BALANCE.
        max_usdc_balance (str): The value for MAX_USDC_BALANCE.
        trading_symbols (str): The value for TRADING_SYMBOLS.
        log_level (str): The value for LOG_LEVEL.
        internet_researcher_enabled (str): The value for INTERNET_RESEARCHER_ENABLED.
        tradingview_webhook_enabled (str): The value for TRADINGVIEW_WEBHOOK_ENABLED.
        tradingview_webhook_port (str): The value for TRADINGVIEW_WEBHOOK_PORT.
        orderbook_analysis_enabled (str): The value for ORDERBOOK_ANALYSIS_ENABLED.
        hedge_enabled (str): The value for HEDGE_ENABLED.
        hedge_ratio (str): The value for HEDGE_RATIO.
        capital_alert_threshold (str): The value for CAPITAL_ALERT_THRESHOLD.

    Returns:
        An HTMLResponse containing a message about the update status.
    """
    # Explicitly collecting form parameters into a dictionary is more robust
    # than relying on locals() and ensures only expected parameters are passed.
    config_data: Dict[str, str] = {
        "BURN_RATE": burn_rate,
        "FAILURE_PROB": failure_prob,
        "GOSSIP_PORT": gossip_port,
        "TOTAL_NODES": total_nodes,
        "PYTHONUNBUFFERED": pythonunbuffered,
        "LLM_MODEL": llm_model,
        "GOSSIP_SIGNING_ENABLED": gossip_signing_enabled,
        "MEMORY_API_ENABLED": memory_api_enabled,
        "MARKET_MODE": market_mode,
        "TEST_WEB3_SWAP_AMOUNT": test_web3_swap_amount,
        "TEST_WEB3_SWAP_SIDE": test_web3_swap_side,
        "WEB3_POOL_FEE": web3_pool_fee,
        "PRICE_SCALE": price_scale,
        "MIN_WETH_BALANCE": min_weth_balance,
        "MIN_ETH_BALANCE": min_eth_balance,
        "MAX_USDC_BALANCE": max_usdc_balance,
        "TRADING_SYMBOLS": trading_symbols,
        "LOG_LEVEL": log_level,
        "INTERNET_RESEARCHER_ENABLED": internet_researcher_enabled,
        "TRADINGVIEW_WEBHOOK_ENABLED": tradingview_webhook_enabled,
        "TRADINGVIEW_WEBHOOK_PORT": tradingview_webhook_port,
        "ORDERBOOK_ANALYSIS_ENABLED": orderbook_analysis_enabled,
        "HEDGE_ENABLED": hedge_enabled,
        "HEDGE_RATIO": hedge_ratio,
        "CAPITAL_ALERT_THRESHOLD": capital_alert_threshold,
    }
    msg: str = update_config(config_data)
    return HTMLResponse(f"<pre>{msg}</pre>")

@router.post("/api/update_secrets")
async def update_secrets(
    web3_private_key: str = Form("", alias="WEB3_PRIVATE_KEY"),
    binance_testnet_api_key: str = Form("", alias="BINANCE_TESTNET_API_KEY"),
    binance_testnet_api_secret: str = Form("", alias="BINANCE_TESTNET_API_SECRET"),
    telegram_bot_token: str = Form("", alias="TELEGRAM_BOT_TOKEN"),
    telegram_chat_id: str = Form("", alias="TELEGRAM_CHAT_ID"),
    etherscan_api_key: str = Form("", alias="ETHERSCAN_API_KEY"),
    web3_rpc_url: str = Form("", alias="WEB3_RPC_URL"),
) -> HTMLResponse:
    """
    Handles the submission of the secrets form, updating the .env file.
    It reads the existing .env file, updates or adds the provided secret keys,
    and writes the changes back while preserving comments and original line order
    as much as possible.

    Args:
        web3_private_key (str): The private key for Web3 operations.
        binance_testnet_api_key (str): Binance Testnet API key.
        binance_testnet_api_secret (str): Binance Testnet API secret.
        telegram_bot_token (str): Telegram bot token.
        telegram_chat_id (str): Telegram chat ID.
        etherscan_api_key (str): Etherscan API key.
        web3_rpc_url (str): Web3 RPC URL.

    Returns:
        An HTMLResponse indicating that secrets have been updated and a restart is needed.
    """
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    env_path: Path = project_root / "mvp" / "lab_swarm_demo" / ".env"

    current_lines: List[str] = []
    if env_path.exists():
        current_lines = env_path.read_text().splitlines()

    # Map form input names (aliased to original env var names) to their values.
    # Only include non-empty values from the form.
    secret_map_from_form: Dict[str, str] = {
        "WEB3_PRIVATE_KEY": web3_private_key,
        "BINANCE_TESTNET_API_KEY": binance_testnet_api_key,
        "BINANCE_TESTNET_API_SECRET": binance_testnet_api_secret,
        "TELEGRAM_BOT_TOKEN": telegram_bot_token,
        "TELEGRAM_CHAT_ID": telegram_chat_id,
        "ETHERSCAN_API_KEY": etherscan_api_key,
        "WEB3_RPC_URL": web3_rpc_url,
    }

    new_lines_output: List[str] = []
    keys_processed_from_form: Set[str] = set()

    for line in current_lines:
        stripped_line: str = line.strip()
        updated_this_line: bool = False

        if not stripped_line or stripped_line.startswith("#"):
            # Preserve empty lines and comments
            new_lines_output.append(line)
            continue

        for key, value in secret_map_from_form.items():
            if stripped_line.startswith(f"{key}="):
                # Update existing key with new value (even if new value is empty)
                new_lines_output.append(f"{key}={value}")
                keys_processed_from_form.add(key)
                updated_this_line = True
                break
        
        if not updated_this_line:
            # If the line was not an updated secret, keep it as is
            new_lines_output.append(line)

    # Append any keys from the form that were not found in the original .env file
    for key, value in secret_map_from_form.items():
        if key not in keys_processed_from_form:
            # Only append if value is not empty, to avoid adding `KEY=` lines unnecessarily
            # if the user just submitted an empty field for a non-existent key.
            # However, if the intent is to allow explicit empty settings, remove this check.
            if value: # Keep original behavior, append even if empty, per `Form("")` default
                new_lines_output.append(f"{key}={value}")

    # Write the updated content back to the .env file, ensuring a trailing newline
    env_path.write_text("\n".join(new_lines_output) + "\n")
    return HTMLResponse("<pre>Secrets updated. Restart swarm to apply.</pre>")

@router.post("/api/approve/{token}")
async def approve_token(token: str) -> HTMLResponse:
    """
    Initiates a token approval script for WETH or USDC.
    The script is executed in a subprocess.

    Args:
        token: The token symbol (e.g., 'WETH', 'USDC') to approve. Case-insensitive.

    Returns:
        An HTMLResponse containing the standard output or error from the approval script.
    """
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    command: List[str]
    token_upper: str = token.upper()

    if token_upper == "WETH":
        command = ["python", "tools/approve_weth.py"]
    elif token_upper == "USDC":
        command = ["python", "tools/approve_usdc.py"]
    else:
        return HTMLResponse(f"<pre>Error: Unknown token '{token}'</pre>", status_code=400)

    # Execute the approval script. Using a list for `cmd` and `shell=False` is safer.
    result: subprocess.CompletedProcess = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=project_root,
        check=False  # Do not raise an exception for non-zero exit codes; capture output instead
    )
    # Return the stdout or stderr from the script execution
    # If there's stdout, return it. Otherwise, return stderr.
    output_message: str = result.stdout.strip() if result.stdout else (result.stderr.strip() if result.stderr else "No output from script.")
    return HTMLResponse(f"<pre>{output_message}</pre>")
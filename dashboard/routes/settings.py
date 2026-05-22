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
    Handles the submission of the secrets form, updating the .env file with the provided values.

    Args:
        web3_private_key (str): The private key for Web3 operations.
        binance_testnet_api_key (str): The API key for Binance Testnet.
        binance_testnet_api_secret (str): The API secret for Binance Testnet.
        telegram_bot_token (str): The token for the Telegram bot.
        telegram_chat_id (str): The chat ID for Telegram notifications.
        etherscan_api_key (str): The API key for Etherscan.
        web3_rpc_url (str): The RPC URL for Web3 operations.

    Returns:
        An HTMLResponse containing a message about the update status.
    """
    env_path = Path(".env")
    if not env_path.exists():
        env_path.touch()

    with env_path.open("r+") as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for line in lines:
            if line.startswith("WEB3_PRIVATE_KEY=") and web3_private_key:
                line = f"WEB3_PRIVATE_KEY={web3_private_key}\n"
            elif line.startswith("BINANCE_TESTNET_API_KEY=") and binance_testnet_api_key:
                line = f"BINANCE_TESTNET_API_KEY={binance_testnet_api_key}\n"
            elif line.startswith("BINANCE_TESTNET_API_SECRET=") and binance_testnet_api_secret:
                line = f"BINANCE_TESTNET_API_SECRET={binance_testnet_api_secret}\n"
            elif line.startswith("TELEGRAM_BOT_TOKEN=") and telegram_bot_token:
                line = f"TELEGRAM_BOT_TOKEN={telegram_bot_token}\n"
            elif line.startswith("TELEGRAM_CHAT_ID=") and telegram_chat_id:
                line = f"TELEGRAM_CHAT_ID={telegram_chat_id}\n"
            elif line.startswith("ETHERSCAN_API_KEY=") and etherscan_api_key:
                line = f"ETHERSCAN_API_KEY={etherscan_api_key}\n"
            elif line.startswith("WEB3_RPC_URL=") and web3_rpc_url:
                line = f"WEB3_RPC_URL={web3_rpc_url}\n"
            f.write(line)

        # Add new variables if they don't exist
        if not any(line.startswith("WEB3_PRIVATE_KEY=") for line in lines) and web3_private_key:
            f.write(f"WEB3_PRIVATE_KEY={web3_private_key}\n")
        if not any(line.startswith("BINANCE_TESTNET_API_KEY=") for line in lines) and binance_testnet_api_key:
            f.write(f"BINANCE_TESTNET_API_KEY={binance_testnet_api_key}\n")
        if not any(line.startswith("BINANCE_TESTNET_API_SECRET=") for line in lines) and binance_testnet_api_secret:
            f.write(f"BINANCE_TESTNET_API_SECRET={binance_testnet_api_secret}\n")
        if not any(line.startswith("TELEGRAM_BOT_TOKEN=") for line in lines) and telegram_bot_token:
            f.write(f"TELEGRAM_BOT_TOKEN={telegram_bot_token}\n")
        if not any(line.startswith("TELEGRAM_CHAT_ID=") for line in lines) and telegram_chat_id:
            f.write(f"TELEGRAM_CHAT_ID={telegram_chat_id}\n")
        if not any(line.startswith("ETHERSCAN_API_KEY=") for line in lines) and etherscan_api_key:
            f.write(f"ETHERSCAN_API_KEY={etherscan_api_key}\n")
        if not any(line.startswith("WEB3_RPC_URL=") for line in lines) and web3_rpc_url:
            f.write(f"WEB3_RPC_URL={web3_rpc_url}\n")

    return HTMLResponse("<pre>Secrets updated successfully.</pre>")

@router.post("/api/approve/{token}")
async def approve_token(token: str) -> HTMLResponse:
    """
    Handles the token approval process for the specified token.

    Args:
        token (str): The token to approve (e.g., 'WETH', 'USDC').

    Returns:
        An HTMLResponse containing a message about the approval status.
    """
    try:
        subprocess.run(["python", "scripts/approve.py", token], check=True)
        return HTMLResponse(f"<pre>Successfully approved {token}.</pre>")
    except subprocess.CalledProcessError as e:
        return HTMLResponse(f"<pre>Failed to approve {token}: {e}</pre>")
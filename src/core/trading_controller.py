"""
TradingController — ончейн-торговля: свопы, авто-конвертация USDC, wrap/unwrap,
принятие решений о входе с учётом ордербука.
"""
import asyncio
from typing import Any, Dict, Optional, Protocol, Union
from loguru import logger
# Assuming swarm_config and adapters.web3_testnet are available and correctly defined
# The actual config object will be provided at runtime or through injection.
# For type hinting purposes, we assume its structure.
from swarm_config import config
from adapters.web3_testnet import WETH_ADDRESS, USDC_ADDRESS

# Define a minimal protocol for the adapter to provide type hinting
# This improves type safety and clarifies the expected interface of the adapter.
class Web3AdapterProtocol(Protocol):
    """
    Protocol defining the expected interface for a Web3 blockchain adapter.
    """
    w3: Any  # Expected to be a web3.Web3 instance
    account: Any  # Expected to be a web3.eth.account instance or similar
    
    async def _get_token_balance(self, token_address: str) -> float:
        """
        Retrieves the balance of a specified ERC-20 token.
        """
        ... # Ellipsis indicates an abstract method in a Protocol

    async def wrap_eth(self, amount: float) -> Dict[str, Any]:
        """
        Wraps ETH into WETH.
        """
        ...

    async def unwrap_weth(self, amount: float) -> Dict[str, Any]:
        """
        Unwraps WETH back into ETH.
        """
        ...

    async def place_order(self, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Places a trading order (buy/sell).
        """
        ...


class TradingController:
    """
    Handles on-chain trading operations including swaps, USDC auto-conversion,
    ETH wrap/unwrap, and making trading decisions based on market data and orderbook.
    """
    def __init__(self, node_id: str):
        """
        Initializes the TradingController with a unique node identifier.

        Args:
            node_id: A string identifier for the trading node.
        """
        self.node_id: str = node_id

    # ------------------------------------------------------------
    # Auxiliary methods
    # ------------------------------------------------------------
    async def check_and_rebalance(self, adapter: Web3AdapterProtocol) -> bool:
        """
        Checks current token balances (WETH, ETH, USDC) and performs necessary
        conversion (USDC to WETH) or wrap/unwrap operations (ETH to WETH or vice versa)
        to maintain desired balance thresholds.

        Args:
            adapter: An adapter object that provides blockchain interaction methods
                     like `_get_token_balance`, `w3`, `account`, `wrap_eth`, `unwrap_weth`, `place_order`.
                     Must conform to `Web3AdapterProtocol`.
        Returns:
            True if a rebalancing transaction was initiated, False otherwise.
        """
        if not adapter or not adapter.account:
            logger.warning(f"[{self.node_id}] Adapter or account not available for rebalance check.")
            return False

        try:
            weth_bal: float = await adapter._get_token_balance(WETH_ADDRESS)
            eth_wei: int = await adapter.w3.eth.get_balance(adapter.account.address)
            eth_bal: float = float(adapter.w3.from_wei(eth_wei, 'ether'))
            usdc_bal: float = await adapter._get_token_balance(USDC_ADDRESS)

            # Retrieve minimum/maximum thresholds from config, providing defaults if not found
            min_weth: float = getattr(config.trading, 'min_weth_balance', 0.1)
            min_eth: float = getattr(config.trading, 'min_eth_balance', 0.05)
            max_usdc: float = getattr(config.trading, 'max_usdc_balance', 100.0)
            
            # Additional small buffer for ETH/WETH operations to avoid gas issues
            WRAP_UNWRAP_BUFFER: float = 0.0005 
            DEFAULT_WRAP_UNWRAP_AMOUNT: float = 0.001 # Default amount to wrap/unwrap if not specified otherwise

            logger.debug(f"[{self.node_id}] Balances: ETH={eth_bal:.4f}, WETH={weth_bal:.4f}, USDC={usdc_bal:.4f}")

            # Priority 1: USDC surplus -> buy WETH if WETH is low
            if usdc_bal > max_usdc and weth_bal < min_weth:
                # Calculate amount to swap, aiming to reduce USDC to max_usdc or fill WETH to min_weth
                # For now, keeping the original fixed amount to preserve functionality, but this could be dynamic
                swap_amount_weth = 0.002 # Original hardcoded value
                logger.info(f"[{self.node_id}] USDC surplus ({usdc_bal:.4f} > {max_usdc:.4f}), buying {swap_amount_weth} WETH.")
                result: Dict[str, Any] = await adapter.place_order("buy", swap_amount_weth)
                logger.info(f"USDC->WETH swap result: {result}")
                return True

            # Priority 2: Wrap ETH if WETH is low and enough ETH is available
            if weth_bal < min_weth and eth_bal > min_eth + WRAP_UNWRAP_BUFFER:
                wrap_amount = DEFAULT_WRAP_UNWRAP_AMOUNT # Could be dynamic: min(eth_bal - min_eth, min_weth - weth_bal)
                logger.info(f"[{self.node_id}] WETH low ({weth_bal:.4f} < {min_weth:.4f}), wrapping {wrap_amount:.4f} ETH.")
                await adapter.wrap_eth(wrap_amount)
                return True

            # Priority 3: Unwrap WETH if ETH is low and enough WETH is available
            if eth_bal < min_eth and weth_bal > min_weth + WRAP_UNWRAP_BUFFER:
                unwrap_amount = DEFAULT_WRAP_UNWRAP_AMOUNT # Could be dynamic: min(weth_bal - min_weth, min_eth - eth_bal)
                logger.info(f"[{self.node_id}] ETH low ({eth_bal:.4f} < {min_eth:.4f}), unwrapping {unwrap_amount:.4f} WETH.")
                await adapter.unwrap_weth(unwrap_amount)
                return True

        except Exception as e:
            logger.error(f"[{self.node_id}] Rebalance error: {e}", exc_info=True)
        return False

    async def execute_swap(self, adapter: Web3AdapterProtocol, side: str, amount: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        Executes a single swap operation using the provided adapter.

        Args:
            adapter: The blockchain interaction adapter conforming to `Web3AdapterProtocol`.
            side: The type of trade, "buy" or "sell".
            amount: The amount of asset to trade.
            price: Optional. The price at which to execute the trade.

        Returns:
            A dictionary containing the result of the swap, or an error message
            if the swap failed.
        """
        try:
            # Ensure amount is positive before attempting a trade
            if amount <= 0:
                logger.warning(f"[{self.node_id}] Attempted to execute swap with non-positive amount: {amount}. Side: {side}")
                return {"error": "Swap amount must be positive."}

            logger.info(f"[{self.node_id}] Executing {side} swap for {amount:.4f} at price {price if price else 'market'}.")
            result: Dict[str, Any] = await adapter.place_order(side, amount, price=price)
            logger.info(f"[{self.node_id}] Swap result: {result}")
            return result
        except Exception as e:
            logger.error(f"[{self.node_id}] Swap exception: {e}", exc_info=True)
            return {"error": str(e)}

    # ------------------------------------------------------------
    # Trading decision making (called from main loop)
    # ------------------------------------------------------------
    def decide_action(
        self,
        market: Dict[str, Any],
        current_params: Dict[str, float],
        capital: float,
        step: int, # Renamed to `_` as it's not used in current logic
        orderbook_imbalance: float = 0.0,
        orderbook_delta_volume: float = 0.0,
    ) -> Dict[str, Union[str, float]]:
        """
        Makes a trading decision (buy/sell) and calculates the corresponding amount
        based on market conditions, strategy parameters, and orderbook data.

        Args:
            market: Dictionary containing current market data, expected to have a "price" key.
            current_params: Dictionary of current strategy parameters, expected to have
                            "max_risk_per_trade".
            capital: The available capital for trading.
            step: The current step or iteration in the trading loop (currently unused).
            orderbook_imbalance: A metric indicating buy/sell pressure from the orderbook
                                 (e.g., positive for buy pressure, negative for sell pressure).
            orderbook_delta_volume: A metric indicating recent volume changes in the orderbook.

        Returns:
            A dictionary specifying the trading action ("buy" or "sell") and the calculated amount.
            Example: {"action": "buy", "amount": 0.5}
        """
        price: float = market.get("price", 100.0)
        # Safely get max_risk_per_trade, default to 0.05 if not found
        max_risk: float = current_params.get("max_risk_per_trade", 0.05)

        # Basic heuristic: if expected return is positive, buy; otherwise, sell.
        # This can be replaced with more complex logic in the future.
        # Ensure config.expected_return_rate exists or provide a default
        expected_return_rate: float = getattr(getattr(config, 'trading', {}), 'expected_return_rate', 0.01) # Default to 1% if not in config
        expected_return: float = price * expected_return_rate
        
        # Decision threshold (e.g., 0.1% of price for buy/sell decision)
        decision_threshold: float = price * 0.001 
        side: str = "buy" if expected_return > decision_threshold else "sell"

        # Base position size: fraction of capital, divided by price
        # Ensure price is not zero to avoid division by zero
        amount: float = (capital * max_risk) / price if price > 0 else 0.0

        # --- Adjustment based on orderbook ---
        # If imbalance is strongly against our direction, reduce position size.
        if side == "buy" and orderbook_imbalance < -0.1:
            logger.debug(
                f"[{self.node_id}] Orderbook: strong sell pressure (imbalance={orderbook_imbalance:.2f}), reducing buy amount"
            )
            amount *= 0.6
        elif side == "sell" and orderbook_imbalance > 0.1:
            logger.debug(
                f"[{self.node_id}] Orderbook: strong buy pressure (imbalance={orderbook_imbalance:.2f}), reducing sell amount"
            )
            amount *= 0.6

        # Protect against too small or negative amounts
        amount = max(0.0, amount)

        return {
            "action": side,
            "amount": amount,
        }

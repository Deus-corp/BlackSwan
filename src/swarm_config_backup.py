"""
SwarmConfig – Centralized configuration using Pydantic Settings v2.
It supports all previous environment variables and attributes for seamless replacement.
"""
import uuid
from typing import List, Optional, Type, Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger # Moved import to top, as print_summary is a core feature


# ---------- Nested Blocks (for organization and grouping) ----------
class TradingSettings(BaseSettings):
    """Settings related to trading parameters."""
    test_web3_swap_amount: float = Field(
        default=0.001, ge=0.0001, alias="TEST_WEB3_SWAP_AMOUNT",
        description="Amount for Web3 test swaps, e.g., for WETH."
    )
    test_web3_swap_side: str = Field(
        default="sell", alias="TEST_WEB3_SWAP_SIDE",
        description="Side for Web3 test swaps ('buy' or 'sell')."
    )
    web3_pool_fee: int = Field(
        default=3000, alias="WEB3_POOL_FEE",
        description="Default pool fee for Web3 decentralized exchanges (e.g., Uniswap v3 format, 3000 = 0.3%)."
    )
    price_scale: int = Field(
        default=10000, alias="PRICE_SCALE",
        description="Multiplier to scale prices, typically used for fixed-point arithmetic or specific exchange APIs."
    )
    min_weth_balance: float = Field(
        default=0.001, ge=0.0, alias="MIN_WETH_BALANCE",
        description="Minimum WETH balance required for operations."
    )
    min_eth_balance: float = Field(
        default=0.002, ge=0.0, alias="MIN_ETH_BALANCE",
        description="Minimum ETH balance required for gas fees and operations."
    )
    max_usdc_balance: float = Field(
        default=100.0, ge=0.0, alias="MAX_USDC_BALANCE",
        description="Maximum USDC balance to hold before rebalancing or taking action."
    )
    max_risk_per_trade: float = Field(
        default=0.01, ge=0.0001, le=0.3,
        description="Maximum percentage of capital to risk per trade."
    )
    take_profit_ratio: float = Field(
        default=2.0, ge=1.0, le=5.0,
        description="Ratio for setting take-profit targets (e.g., 2.0 means 2x risk amount)."
    )
    min_confidence: float = Field(
        default=0.65, ge=0.3, le=0.98,
        description="Minimum confidence score required to execute a trade."
    )

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    max_drawdown_limit: float = Field(default=0.1, ge=0.0, le=1.0)
    max_exposure_per_asset: float = Field(default=0.25, ge=0.0, le=1.0)
    risk_per_trade_fraction: float = Field(default=0.01, ge=0.0, le=0.1)


class LLMSettings(BaseSettings):
    """Settings for Large Language Models."""
    model_name: str = Field(
        default="deepseek", alias="LLM_MODEL",
        description="Name of the LLM model to use (e.g., 'deepseek', 'gpt-4')."
    )
    temperature: float = Field(
        default=0.35, ge=0.0, le=1.0,
        description="LLM temperature for response randomness (0.0 for deterministic, 1.0 for creative)."
    )
    max_tokens_mutation: int = Field(
        default=250, ge=50, le=800,
        description="Maximum number of tokens for LLM mutation or response generation."
    )

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


class SecuritySettings(BaseSettings):
    """Security-related settings, primarily API keys and private keys."""
    web3_private_key: Optional[SecretStr] = Field(
        default=None, alias="WEB3_PRIVATE_KEY",
        description="Private key for Web3 operations, stored securely."
    )
    binance_testnet_api_key: Optional[SecretStr] = Field(
        default=None, alias="BINANCE_TESTNET_API_KEY",
        description="API key for Binance Testnet."
    )
    binance_testnet_api_secret: Optional[SecretStr] = Field(
        default=None, alias="BINANCE_TESTNET_API_SECRET",
        description="API secret for Binance Testnet."
    )
    etherscan_api_key: Optional[SecretStr] = Field(
        default=None, alias="ETHERSCAN_API_KEY",
        description="API key for Etherscan, used for blockchain data queries."
    )
    telegram_bot_token: Optional[SecretStr] = Field(
        default=None, alias="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token for sending notifications."
    )
    telegram_chat_id: Optional[SecretStr] = Field(
        default=None, alias="TELEGRAM_CHAT_ID",
        description="Telegram chat ID for receiving bot notifications."
    )

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @field_validator("web3_private_key", "binance_testnet_api_secret", mode="before")
    @classmethod
    def ensure_secret(cls: Type[Any], v: Optional[str | SecretStr]) -> Optional[SecretStr]:
        """
        Ensures that sensitive string values are wrapped in Pydantic's SecretStr.
        This helps prevent accidental logging or exposure of secrets.

        Args:
            cls (Type[Any]): The class itself (implicit in @classmethod).
            v (Optional[str | SecretStr]): The value to validate, which can be a string or already a SecretStr.

        Returns:
            Optional[SecretStr]: The value wrapped in SecretStr, or None if the input was None.
        """
        if isinstance(v, str) and v:
            return SecretStr(v)
        if isinstance(v, SecretStr): # If it's already a SecretStr, return it as is.
            return v
        return None # Return None if v is None or an empty string


class SwarmConfig(BaseSettings):
    """
    Main configuration class for the Swarm application.
    It consolidates various settings into a single, accessible object,
    loading from .env files and environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Used for nested environment variables, e.g., LLM__MODEL
        extra="ignore",             # Ignore extra environment variables not defined here
        case_sensitive=False,       # Environment variables are case-insensitive
    )

    # ----- Core Settings (from old SwarmConfig) -----
    node_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), alias="NODE_ID",
        description="Unique identifier for this node in the Swarm."
    )
    port: int = Field(
        default=8000, alias="PORT",
        description="Port on which the main application service runs (e.g., FastAPI)."
    )
    environment: str = Field(
        default="development", pattern="^(development|staging|production)$", alias="ENVIRONMENT",
        description="Application environment (development, staging, or production)."
    )
    market_url: Optional[str] = Field(
        default=None, alias="MARKET_URL",  # For backward compatibility
        description="URL for the market service endpoint (deprecated, kept for compatibility)."
    )
    burn_rate: float = Field(
        default=0.5, ge=0.0, le=1.0, alias="BURN_RATE",
        description="Rate at which internal resources or simulated capital is 'burned'."
    )
    failure_prob: float = Field(
        default=0.0, ge=0.0, le=0.3, alias="FAILURE_PROB",
        description="Probability of a simulated failure occurring."
    )
    gossip_interval: float = Field(
        default=1.0, ge=0.1, le=10.0, alias="GOSSIP_INTERVAL",
        description="Interval (in seconds) between gossip messages for peer discovery."
    )
    max_state: int = Field(
        default=200, alias="MAX_STATE",
        description="Maximum number of states to retain in a state machine or CRDT."
    )
    ttl: int = Field(
        default=300, alias="TTL",
        description="Time-to-live (in seconds) for certain cached items or messages."
    )
    max_import: int = Field(
        default=2, alias="MAX_IMPORT",
        description="Maximum number of imports allowed in a specific context."
    )
    import_cooldown: int = Field(
        default=5, alias="IMPORT_COOLDOWN",
        description="Cooldown period (in seconds) between import operations."
    )

    # Additional old fields
    expected_return_rate: float = Field(
        default=20.0, alias="EXPECTED_RETURN_RATE",
        description="Expected annual return rate percentage (e.g., 20.0 for 20%)."
    )
    max_normalized_capital: float = Field(
        default=10000.0, alias="MAX_NORMALIZED_CAPITAL",
        description="Maximum normalized capital for internal calculations or simulations."
    )

    # ----- Gossip & Service -----
    gossip_port: int = Field(
        default=9777, alias="GOSSIP_PORT",
        description="Port for the gossip protocol service."
    )
    total_nodes: int = Field(
        default=4, alias="TOTAL_NODES",
        description="Total number of nodes expected in the Swarm network."
    )

    gossip_max_clock_skew_ms: int = Field(default=10_000, alias="GOSSIP_MAX_CLOCK_SKEW_MS")
    meta_agent_reflect_interval: int = Field(default=100, alias="META_AGENT_REFLECT_INTERVAL")
    meta_agent_learn_interval: int = Field(default=1000, alias="META_AGENT_LEARN_INTERVAL")

    gossip_signing_enabled: bool = Field(
        default=True, alias="GOSSIP_SIGNING_ENABLED",
        description="Enable/disable cryptographic signing of gossip messages."
    )
    memory_api_enabled: bool = Field(
        default=True, alias="MEMORY_API_ENABLED",
        description="Enable/disable the internal memory API."
    )
    market_mode: str = Field(
        default="web3", alias="MARKET_MODE",
        description="Operating mode for market interactions ('web3', 'binance_testnet', 'simulated', etc.)."
    )
    trading_symbols: str = Field(
        default="WETH/USDC", alias="TRADING_SYMBOLS",
        description="Comma-separated list of trading symbols (e.g., 'WETH/USDC,BTC/USDT')."
    )
    log_level: str = Field(
        default="INFO", alias="LOG_LEVEL",
        description="Minimum log level for application logging (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR')."
    )

    # ----- Features flags -----
    internet_researcher_enabled: bool = Field(
        default=True, alias="INTERNET_RESEARCHER_ENABLED",
        description="Enable/disable the internet researcher component."
    )
    tradingview_webhook_enabled: bool = Field(
        default=True, alias="TRADINGVIEW_WEBHOOK_ENABLED",
        description="Enable/disable the TradingView webhook listener."
    )
    tradingview_webhook_port: int = Field(
        default=8888, alias="TRADINGVIEW_WEBHOOK_PORT",
        description="Port for the TradingView webhook listener."
    )
    orderbook_analysis_enabled: bool = Field(
        default=False, alias="ORDERBOOK_ANALYSIS_ENABLED",
        description="Enable/disable real-time order book analysis."
    )
    hedge_enabled: bool = Field(
        default=True, alias="HEDGE_ENABLED",
        description="Enable/disable hedging strategies."
    )
    hedge_ratio: float = Field(
        default=0.5, alias="HEDGE_RATIO",
        description="Ratio for hedging operations (e.g., 0.5 means hedge 50% of exposure)."
    )
    capital_alert_threshold: float = Field(
        default=100.0, alias="CAPITAL_ALERT_THRESHOLD",
        description="Threshold below which a capital alert is triggered."
    )
    quarantine_enabled: bool = Field(
        default=False, alias="QUARANTINE_ENABLED",
        description="Enable/disable node quarantine mechanism."
    )
    # ----- Paths for data storage -----
    event_ledger_path: str = Field(
        default="./data/ledgers/events.jsonl",
        alias="EVENT_LEDGER_PATH",
        description="File path for the event ledger (JSONL format)."
    )
    event_sqlite_path: str = Field(
        default="./data/ledgers/events.db",
        alias="EVENT_SQLITE_PATH",
        description="File path for the event ledger (SQLite database)."
    )

    crdt_db_path: str = Field(
        default="./crdt_state.db", alias="CRDT_DB_PATH",
        description="File path for the CRDT (Conflict-free Replicated Data Type) state database."
    )

    # ----- Web3 -----
    web3_rpc_url: str = Field(
        default="https://ethereum-sepolia.publicnode.com", alias="WEB3_RPC_URL",
        description="URL for the Web3 RPC endpoint (e.g., Ethereum Sepolia)."
    )

    # ----- Redis (for market_service) -----
    redis_url: str = Field(
        default="redis://localhost:6379", alias="REDIS_URL",
        description="URL for the Redis instance, typically used by market services."
    )

    # ----- Nested Groups -----
    trading: TradingSettings = Field(
        default_factory=TradingSettings,
        description="Nested trading-related settings."
    )
    llm: LLMSettings = Field(
        default_factory=LLMSettings,
        description="Nested LLM-related settings."
    )
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Nested security-related settings (e.g., API keys)."
    )

    # ----- PEERS Parser -----
    peers_raw: str = Field(
        default="", alias="PEERS",
        description="Raw comma-separated string of peer addresses (e.g., 'host1:port,host2:port')."
    )

    # ----- Compatibility with old code (aliases via properties) -----
    # These properties provide backward compatibility for code that might
    # still access configuration attributes using their uppercase, underscored names.

    @property
    def NODE_ID(self: "SwarmConfig") -> str:
        """Backward compatibility property for node_id."""
        return self.node_id

    @property
    def PORT(self: "SwarmConfig") -> int:
        """Backward compatibility property for port."""
        return self.port

    @property
    def PEERS(self: "SwarmConfig") -> List[str]:
        """Parses the raw peers string into a list of individual peer addresses."""
        return [p.strip() for p in self.peers_raw.split(",") if p.strip()]

    @property
    def MARKET_URL(self: "SwarmConfig") -> Optional[str]:
        """Backward compatibility property for market_url."""
        return self.market_url

    @property
    def BURN_RATE(self: "SwarmConfig") -> float:
        """Backward compatibility property for burn_rate."""
        return self.burn_rate

    @property
    def FAILURE_PROB(self: "SwarmConfig") -> float:
        """Backward compatibility property for failure_prob."""
        return self.failure_prob

    @property
    def GOSSIP_INTERVAL(self: "SwarmConfig") -> float:
        """Backward compatibility property for gossip_interval."""
        return self.gossip_interval

    @property
    def MAX_STATE(self: "SwarmConfig") -> int:
        """Backward compatibility property for max_state."""
        return self.max_state

    @property
    def TTL(self: "SwarmConfig") -> int:
        """Backward compatibility property for ttl."""
        return self.ttl

    @property
    def MAX_IMPORT(self: "SwarmConfig") -> int:
        """Backward compatibility property for max_import."""
        return self.max_import

    @property
    def IMPORT_COOLDOWN(self: "SwarmConfig") -> int:
        """Backward compatibility property for import_cooldown."""
        return self.import_cooldown

    @property
    def EXPECTED_RETURN_RATE(self: "SwarmConfig") -> float:
        """Backward compatibility property for expected_return_rate."""
        return self.expected_return_rate

    @property
    def MAX_NORMALIZED_CAPITAL(self: "SwarmConfig") -> float:
        """Backward compatibility property for max_normalized_capital."""
        return self.max_normalized_capital
    
    @property
    def EVENT_LEDGER_PATH(self: "SwarmConfig") -> str:
        """Backward compatibility property for event_ledger_path."""
        return self.event_ledger_path

    @property
    def EVENT_SQLITE_PATH(self: "SwarmConfig") -> str:
        """Backward compatibility property for event_sqlite_path."""
        return self.event_sqlite_path

    @property
    def CRDT_DB_PATH(self: "SwarmConfig") -> str:
        """Backward compatibility property for crdt_db_path."""
        return self.crdt_db_path

    # Helper Methods
    def is_production(self: "SwarmConfig") -> bool:
        """
        Checks if the current environment is set to 'production'.

        Returns:
            bool: True if environment is 'production', False otherwise.
        """
        return self.environment == "production"

    def print_summary(self: "SwarmConfig") -> None:
        """
        Prints a summary of the current Swarm configuration to the console
        using the loguru logger.
        """
        logger.info(f"Node ID: {self.node_id[:8]}... | Env: {self.environment}")
        logger.info(f"Peers: {len(self.PEERS)} | RPC: {self.web3_rpc_url}")
        logger.info(f"LLM: {self.llm.model_name} | Risk: {self.trading.max_risk_per_trade}")


# ---------- Singleton (replacement for old config access) ----------
# This instance ensures that the configuration is loaded once and
# is globally accessible throughout the application.
config: SwarmConfig = SwarmConfig()

"""
SwarmConfig — централизованная конфигурация на Pydantic Settings v2.
Поддерживает все прежние переменные окружения и атрибуты для бесшовной замены.
"""
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import uuid

# ---------- Вложенные блоки (для красоты и группировки) ----------
class TradingSettings(BaseSettings):
    """Настройки, связанные с торговлей."""
    test_web3_swap_amount: float = Field(default=0.001, ge=0.0001, alias="TEST_WEB3_SWAP_AMOUNT")
    test_web3_swap_side: str = Field(default="sell", alias="TEST_WEB3_SWAP_SIDE")
    web3_pool_fee: int = Field(default=3000, alias="WEB3_POOL_FEE")
    price_scale: int = Field(default=10000, alias="PRICE_SCALE")
    min_weth_balance: float = Field(default=0.001, ge=0.0, alias="MIN_WETH_BALANCE")
    min_eth_balance: float = Field(default=0.002, ge=0.0, alias="MIN_ETH_BALANCE")
    max_usdc_balance: float = Field(default=100.0, ge=0.0, alias="MAX_USDC_BALANCE")
    max_risk_per_trade: float = Field(default=0.01, ge=0.0001, le=0.3)
    take_profit_ratio: float = Field(default=2.0, ge=1.0, le=5.0)
    min_confidence: float = Field(default=0.65, ge=0.3, le=0.98)

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


class LLMSettings(BaseSettings):
    model_name: str = Field(default="deepseek", alias="LLM_MODEL")
    temperature: float = Field(default=0.35, ge=0.0, le=1.0)
    max_tokens_mutation: int = Field(default=250, ge=50, le=800)

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


class SecuritySettings(BaseSettings):
    web3_private_key: Optional[SecretStr] = Field(default=None, alias="WEB3_PRIVATE_KEY")
    binance_testnet_api_key: Optional[SecretStr] = Field(default=None, alias="BINANCE_TESTNET_API_KEY")
    binance_testnet_api_secret: Optional[SecretStr] = Field(default=None, alias="BINANCE_TESTNET_API_SECRET")
    etherscan_api_key: Optional[SecretStr] = Field(default=None, alias="ETHERSCAN_API_KEY")
    telegram_bot_token: Optional[SecretStr] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[SecretStr] = Field(default=None, alias="TELEGRAM_CHAT_ID")

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @field_validator("web3_private_key", "binance_testnet_api_secret", mode="before")
    @classmethod
    def ensure_secret(cls, v):
        if isinstance(v, str) and v:
            return SecretStr(v)
        return v


class SwarmConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",   # для будущих вложенных переменных, если понадобятся
        extra="ignore",
        case_sensitive=False,
    )

    # ----- Основные (из старого SwarmConfig) -----
    node_id: str = Field(default_factory=lambda: str(uuid.uuid4()), alias="NODE_ID")
    port: int = Field(default=8000, alias="PORT")
    environment: str = Field(default="development", pattern="^(development|staging|production)$", alias="ENVIRONMENT")
    market_url: Optional[str] = Field(default=None, alias="MARKET_URL")   # для обратной совместимости
    burn_rate: float = Field(default=0.5, ge=0.0, le=1.0, alias="BURN_RATE")
    failure_prob: float = Field(default=0.0, ge=0.0, le=0.3, alias="FAILURE_PROB")
    gossip_interval: float = Field(default=1.0, ge=0.1, le=10.0, alias="GOSSIP_INTERVAL")
    max_state: int = Field(default=200, alias="MAX_STATE")
    ttl: int = Field(default=300, alias="TTL")
    max_import: int = Field(default=2, alias="MAX_IMPORT")
    import_cooldown: int = Field(default=5, alias="IMPORT_COOLDOWN")

    # Доп. старые поля
    expected_return_rate: float = Field(default=20.0, alias="EXPECTED_RETURN_RATE")
    max_normalized_capital: float = Field(default=10000.0)

    # ----- Gossip & Service -----
    gossip_port: int = Field(default=9777, alias="GOSSIP_PORT")
    total_nodes: int = Field(default=4, alias="TOTAL_NODES")
    gossip_signing_enabled: bool = Field(default=True, alias="GOSSIP_SIGNING_ENABLED")
    memory_api_enabled: bool = Field(default=True, alias="MEMORY_API_ENABLED")
    market_mode: str = Field(default="web3", alias="MARKET_MODE")
    trading_symbols: str = Field(default="WETH/USDC", alias="TRADING_SYMBOLS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ----- Features flags -----
    internet_researcher_enabled: bool = Field(default=True, alias="INTERNET_RESEARCHER_ENABLED")
    tradingview_webhook_enabled: bool = Field(default=True, alias="TRADINGVIEW_WEBHOOK_ENABLED")
    tradingview_webhook_port: int = Field(default=8888, alias="TRADINGVIEW_WEBHOOK_PORT")
    orderbook_analysis_enabled: bool = Field(default=False, alias="ORDERBOOK_ANALYSIS_ENABLED")
    hedge_enabled: bool = Field(default=True, alias="HEDGE_ENABLED")
    hedge_ratio: float = Field(default=0.5, alias="HEDGE_RATIO")
    capital_alert_threshold: float = Field(default=100.0, alias="CAPITAL_ALERT_THRESHOLD")

    # ----- Web3 -----
    web3_rpc_url: str = Field(default="https://ethereum-sepolia.publicnode.com", alias="WEB3_RPC_URL")

    # ----- Redis (для market_service) -----
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # ----- Вложенные группы -----
    trading: TradingSettings = Field(default_factory=TradingSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    # ----- Парсер PEERS -----
    peers_raw: str = Field(default="", alias="PEERS")

    # ----- Совместимость со старым кодом (псвеонимы) -----
    @property
    def NODE_ID(self) -> str:
        return self.node_id

    @property
    def PORT(self) -> int:
        return self.port

    @property
    def PEERS(self) -> List[str]:
        return [p.strip() for p in self.peers_raw.split(",") if p.strip()]

    @property
    def MARKET_URL(self) -> Optional[str]:
        return self.market_url

    @property
    def BURN_RATE(self) -> float:
        return self.burn_rate

    @property
    def FAILURE_PROB(self) -> float:
        return self.failure_prob

    @property
    def GOSSIP_INTERVAL(self) -> float:
        return self.gossip_interval

    @property
    def MAX_STATE(self) -> int:
        return self.max_state

    @property
    def TTL(self) -> int:
        return self.ttl

    @property
    def MAX_IMPORT(self) -> int:
        return self.max_import

    @property
    def IMPORT_COOLDOWN(self) -> int:
        return self.import_cooldown

    @property
    def EXPECTED_RETURN_RATE(self) -> float:
        return self.expected_return_rate

    @property
    def MAX_NORMALIZED_CAPITAL(self) -> float:
        return self.max_normalized_capital

    # Вспомогательные методы
    def is_production(self) -> bool:
        return self.environment == "production"

    def print_summary(self):
        from loguru import logger
        logger.info(f"Node ID: {self.node_id[:8]}... | Env: {self.environment}")
        logger.info(f"Peers: {len(self.PEERS)} | RPC: {self.web3_rpc_url}")
        logger.info(f"LLM: {self.llm.model_name} | Risk: {self.trading.max_risk_per_trade}")


# ---------- Синглтон (замена старого) ----------
config = SwarmConfig()
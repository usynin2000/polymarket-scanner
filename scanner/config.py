"""Configuration settings for the scanner."""

from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings

from scanner.domain.models import MarketCategory


class ScannerConfig(BaseSettings):
    """Scanner configuration with environment variable support."""

    # WebSocket settings
    ws_url: str = Field(
        default="wss://ws-subscriptions-clob.polymarket.com/ws/market",
        description="Polymarket CLOB WebSocket URL for market data",
    )
    ws_reconnect_delay: float = Field(default=5.0, description="Reconnect delay in seconds")
    ws_ping_interval: float = Field(default=30.0, description="Ping interval in seconds")

    # Filter settings
    min_trade_size_usd: Decimal = Field(
        default=Decimal("2000"), description="Minimum trade size in USD"
    )

    # Excluded categories (sports, crypto, time-based by default)
    excluded_categories: list[MarketCategory] = Field(
        default=[
            MarketCategory.SPORTS,
            MarketCategory.CRYPTO,
            MarketCategory.TIME_BASED,
        ],
        description="Categories to exclude from scanning",
    )

    # LP detection settings
    lp_balance_threshold: Decimal = Field(
        default=Decimal("0.1"),
        description="Threshold for balanced position detection (10%)",
    )
    lp_repetition_window: int = Field(
        default=10, description="Number of trades to check for repetitive behavior"
    )

    # Signal detection settings
    fresh_wallet_trade_threshold: int = Field(
        default=5, description="Max trades for fresh wallet detection"
    )
    size_anomaly_multiplier: Decimal = Field(
        default=Decimal("3.0"),
        description="Multiplier for size anomaly detection",
    )
    clustering_time_window: int = Field(
        default=300, description="Time window for clustering detection (seconds)"
    )
    clustering_min_trades: int = Field(
        default=3, description="Minimum trades for clustering detection"
    )

    # Output settings
    log_level: str = Field(default="INFO", description="Logging level")

    # Telegram settings
    telegram_bot_token: str | None = Field(
        default=None,
        description="Telegram bot token from @BotFather",
    )
    telegram_chat_id: str | None = Field(
        default=None,
        description="Telegram chat ID to send alerts to",
    )
    telegram_enabled: bool = Field(
        default=True,
        description="Enable Telegram notifications (requires bot_token and chat_id)",
    )

    # Polymarket API credentials (for authenticated access)
    private_key: str | None = Field(
        default=None,
        description="Ethereum private key for CLOB API authentication",
    )
    chain_id: int = Field(
        default=137,
        description="Chain ID (137 for Polygon mainnet)",
    )

    model_config = {
        "env_prefix": "SCANNER_",
        "env_file": ".env",
        "extra": "ignore",
    }


# Global config instance
config = ScannerConfig()


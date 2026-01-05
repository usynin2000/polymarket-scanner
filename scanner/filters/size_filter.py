"""Trade size filter."""

from decimal import Decimal

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Trade
from scanner.filters.base import FilterResult, TradeFilter


class SizeFilter(TradeFilter):
    """
    Filter trades based on USD size.

    Discards trades below minimum threshold (default $2,000).
    """

    def __init__(self, config: ScannerConfig | None = None):
        """
        Initialize size filter.

        Args:
            config: Scanner configuration. Uses default if not provided.
        """
        self._config = config or default_config
        self._min_size = self._config.min_trade_size_usd

    @property
    def name(self) -> str:
        """Filter name."""
        return "SizeFilter"

    async def check(self, trade: Trade) -> FilterResult:
        """
        Check if trade size meets minimum threshold.

        Args:
            trade: Trade to check.

        Returns:
            FilterResult - rejected if size is below minimum.
        """
        if trade.size_usd < self._min_size:
            return FilterResult.reject(
                f"Trade size ${trade.size_usd:.2f} below minimum ${self._min_size:.2f}"
            )

        return FilterResult.accept()

    def set_minimum_size(self, size: Decimal) -> None:
        """Update minimum trade size threshold."""
        self._min_size = size


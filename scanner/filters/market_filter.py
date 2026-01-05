"""Market category filter."""

import logging

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Market, MarketCategory, Trade
from scanner.filters.base import FilterResult, TradeFilter
from scanner.services.market_service import MarketService


logger = logging.getLogger(__name__)


class MarketFilter(TradeFilter):
    """
    Filter trades based on market category.

    Discards trades from excluded categories like sports, crypto, time-based.
    Automatically fetches market data if not attached to trade.
    """

    def __init__(
        self, 
        config: ScannerConfig | None = None,
        market_service: MarketService | None = None,
    ):
        """
        Initialize market filter.

        Args:
            config: Scanner configuration. Uses default if not provided.
            market_service: Service for fetching market data. Creates new if not provided.
        """
        self._config = config or default_config
        self._excluded = set(self._config.excluded_categories)
        self._market_service = market_service or MarketService()

    @property
    def name(self) -> str:
        """Filter name."""
        return "MarketFilter"

    async def check(self, trade: Trade) -> FilterResult:
        """
        Check if trade's market category is allowed.

        Args:
            trade: Trade to check.

        Returns:
            FilterResult - rejected if market category is excluded.
        """
        # Fetch market data if not attached
        market = trade.market
        if market is None:
            market = await self._market_service.get_market(
                trade.market_id,
                raw_data=trade.raw_data,
            )
            
            if market is None:
                logger.debug(f"Could not fetch market for trade {trade.id}")
                return FilterResult.reject("Market data not available")
            
            # Attach market to trade for downstream processing
            trade.market = market

        category = market.category
        
        logger.debug(
            f"Market '{market.question[:50]}...' category: {category.value}"
        )

        if category in self._excluded:
            return FilterResult.reject(
                f"Market category '{category.value}' is excluded"
            )

        # Check if market is still active
        if not market.is_active:
            return FilterResult.reject("Market is no longer active")

        return FilterResult.accept()

    def add_excluded_category(self, category: MarketCategory) -> None:
        """Add a category to exclusion list."""
        self._excluded.add(category)

    def remove_excluded_category(self, category: MarketCategory) -> None:
        """Remove a category from exclusion list."""
        self._excluded.discard(category)


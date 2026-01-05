"""Market data service."""

from datetime import datetime, timedelta
from decimal import Decimal

from scanner.domain.models import Market, MarketCategory


class MarketService:
    """
    Service for fetching and caching market data.

    TODO: Replace mock implementation with real Polymarket API calls.
    """

    def __init__(self):
        """Initialize market service."""
        self._cache: dict[str, Market] = {}

    async def get_market(self, market_id: str) -> Market | None:
        """
        Get market data by ID.

        Args:
            market_id: Market ID to lookup.

        Returns:
            Market data or None if not found.
        """
        if market_id in self._cache:
            return self._cache[market_id]

        market = await self._fetch_market(market_id)
        if market:
            self._cache[market_id] = market

        return market

    async def _fetch_market(self, market_id: str) -> Market | None:
        """
        Fetch market data from Polymarket API.

        TODO: Implement real API call to Polymarket CLOB API:
        - GET https://clob.polymarket.com/markets/{market_id}

        Args:
            market_id: Market to fetch.

        Returns:
            Market data or None.
        """
        # MOCK: Generate market based on ID
        id_hash = hash(market_id)

        categories = list(MarketCategory)
        category = categories[id_hash % len(categories)]

        # Generate mock odds
        odds_yes = Decimal(str(30 + (id_hash % 40))) / 100
        odds_no = 1 - odds_yes

        return Market(
            id=market_id,
            question=f"Mock market question for {market_id[:8]}...?",
            category=category,
            end_date=datetime.now() + timedelta(days=id_hash % 30),
            current_odds_yes=odds_yes,
            current_odds_no=odds_no,
            volume_24h=Decimal(str(10000 + (id_hash % 100000))),
            liquidity=Decimal(str(50000 + (id_hash % 200000))),
            metadata={"mock": True},
        )

    async def update_odds(
        self,
        market_id: str,
        odds_yes: Decimal,
        odds_no: Decimal,
    ) -> None:
        """
        Update cached market odds.

        Args:
            market_id: Market to update.
            odds_yes: New YES odds.
            odds_no: New NO odds.
        """
        if market_id in self._cache:
            market = self._cache[market_id]
            self._cache[market_id] = Market(
                id=market.id,
                question=market.question,
                category=market.category,
                end_date=market.end_date,
                current_odds_yes=odds_yes,
                current_odds_no=odds_no,
                volume_24h=market.volume_24h,
                liquidity=market.liquidity,
                metadata=market.metadata,
            )

    def clear_cache(self) -> None:
        """Clear market cache."""
        self._cache.clear()


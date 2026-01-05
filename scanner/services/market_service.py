"""Market data service."""

import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

import aiohttp

from scanner.domain.models import Market, MarketCategory


logger = logging.getLogger(__name__)

# Keywords for category detection
CATEGORY_KEYWORDS: dict[MarketCategory, list[str]] = {
    MarketCategory.CRYPTO: [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "sol",
        "xrp", "ripple", "dogecoin", "doge", "cardano", "ada", "polygon",
        "matic", "avalanche", "avax", "chainlink", "link", "uniswap",
        "shiba", "pepe", "memecoin", "defi", "nft", "blockchain",
        "binance", "coinbase", "token", "altcoin", "stablecoin",
    ],
    MarketCategory.SPORTS: [
        "nfl", "nba", "mlb", "nhl", "soccer", "football", "basketball",
        "baseball", "hockey", "tennis", "golf", "ufc", "mma", "boxing",
        "f1", "formula", "nascar", "olympics", "world cup", "super bowl",
        "championship", "playoffs", "finals", "match", "game score",
        "winner", "mvp", "player", "team", "league", "season",
        "patriots", "lakers", "yankees", "cowboys", "warriors",
    ],
    MarketCategory.TIME_BASED: [
        "by end of", "before midnight", "by december", "by january",
        "by february", "by march", "by april", "by may", "by june",
        "by july", "by august", "by september", "by october", "by november",
        "this week", "this month", "this year", "next week", "next month",
        "deadline", "by when", "date of",
    ],
    MarketCategory.ENTERTAINMENT: [
        "movie", "film", "oscar", "grammy", "emmy", "golden globe",
        "box office", "netflix", "disney", "marvel", "celebrity",
        "kardashian", "taylor swift", "album", "song", "concert",
        "tv show", "series", "streaming", "youtube", "tiktok",
    ],
    MarketCategory.SCIENCE: [
        "spacex", "nasa", "climate", "ai ", "artificial intelligence",
        "research", "discovery", "vaccine", "fda", "cdc", "who",
        "pandemic", "virus", "scientific", "study", "experiment",
    ],
    MarketCategory.ECONOMICS: [
        "fed ", "federal reserve", "interest rate", "inflation",
        "gdp", "unemployment", "recession", "stock market", "s&p",
        "nasdaq", "dow jones", "earnings", "ipo", "bankruptcy",
    ],
    MarketCategory.POLITICS: [
        "trump", "biden", "election", "vote", "congress", "senate",
        "house", "president", "governor", "poll", "democrat", "republican",
        "legislation", "bill", "law", "supreme court", "political",
        "cabinet", "administration", "impeach", "indictment",
    ],
}


class MarketService:
    """
    Service for fetching and caching market data from Polymarket APIs.
    
    Uses Gamma API for market metadata and CLOB API for trading data.
    """

    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"

    def __init__(self):
        """Initialize market service."""
        self._cache: dict[str, Market] = {}
        self._condition_to_market: dict[str, str] = {}

    async def get_market(self, market_id: str, raw_data: dict[str, Any] | None = None) -> Market | None:
        """
        Get market data by ID.

        Args:
            market_id: Market ID to lookup (can be condition_id or token_id).
            raw_data: Optional raw trade data with market_info from WebSocket.

        Returns:
            Market data or None if not found.
        """
        if market_id in self._cache:
            return self._cache[market_id]

        # Try to extract market info from raw WebSocket data first
        market = None
        if raw_data and "market_info" in raw_data:
            market = self._parse_market_info(market_id, raw_data["market_info"])
        
        # If no market info in raw_data, fetch from API
        if not market:
            market = await self._fetch_market(market_id)
        
        if market:
            self._cache[market_id] = market

        return market

    def _parse_market_info(self, market_id: str, market_info: dict[str, Any]) -> Market | None:
        """
        Parse market info from WebSocket cached data.
        
        Args:
            market_id: Market identifier.
            market_info: Market data from _asset_to_market cache.
            
        Returns:
            Market object or None.
        """
        if not market_info:
            return None
            
        try:
            # Get question from different API formats
            question = (
                market_info.get("question") or 
                market_info.get("description") or
                market_info.get("title") or
                ""
            )
            
            # Get tags (Gamma API)
            tags = market_info.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            
            # Determine category
            category = self._detect_category(question, tags)
            
            # Parse end date
            end_date = None
            end_date_str = market_info.get("endDate") or market_info.get("end_date_iso")
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            
            # Parse odds from tokens
            odds_yes = Decimal("0.5")
            odds_no = Decimal("0.5")
            
            tokens = market_info.get("tokens", [])
            for token in tokens:
                outcome = token.get("outcome", "").upper()
                price = token.get("price")
                if price:
                    if outcome == "YES":
                        odds_yes = Decimal(str(price))
                    elif outcome == "NO":
                        odds_no = Decimal(str(price))
            
            # Get volume and liquidity
            volume_24h = Decimal(str(market_info.get("volume24hr", 0) or 0))
            liquidity = Decimal(str(market_info.get("liquidity", 0) or 0))
            
            return Market(
                id=market_id,
                question=question,
                category=category,
                end_date=end_date,
                current_odds_yes=odds_yes,
                current_odds_no=odds_no,
                volume_24h=volume_24h,
                liquidity=liquidity,
                metadata={
                    "tags": tags,
                    "condition_id": market_info.get("condition_id"),
                    "slug": market_info.get("slug"),
                },
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse market info for {market_id}: {e}")
            return None

    async def _fetch_market(self, market_id: str) -> Market | None:
        """
        Fetch market data from Polymarket Gamma API.

        Args:
            market_id: Market to fetch (condition_id or slug).

        Returns:
            Market data or None.
        """
        async with aiohttp.ClientSession() as session:
            # Try Gamma API first (has more metadata)
            try:
                # First try to get by condition_id
                url = f"{self.GAMMA_API}/markets?condition_id={market_id}"
                logger.debug(f"Fetching market from {url}")
                
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and len(data) > 0:
                            return self._parse_market_info(market_id, data[0])
                
                # Try by slug as fallback
                url = f"{self.GAMMA_API}/markets/{market_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return self._parse_market_info(market_id, data)
                            
            except Exception as e:
                logger.warning(f"Gamma API request failed for {market_id}: {e}")
            
            # Try CLOB API as fallback
            try:
                url = f"{self.CLOB_API}/markets/{market_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:
                            return self._parse_market_info(market_id, data)
                            
            except Exception as e:
                logger.warning(f"CLOB API request failed for {market_id}: {e}")
        
        logger.warning(f"Could not fetch market data for {market_id}")
        return None

    def _detect_category(self, question: str, tags: list[str]) -> MarketCategory:
        """
        Detect market category from question text and tags.
        
        Args:
            question: Market question/description.
            tags: List of tags from API.
            
        Returns:
            Detected MarketCategory.
        """
        text = (question + " " + " ".join(tags)).lower()
        
        # Check for each category by keywords
        category_scores: dict[MarketCategory, int] = {}
        
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = 0
            for keyword in keywords:
                # Use word boundary matching for short keywords
                if len(keyword) <= 4:
                    pattern = rf'\b{re.escape(keyword)}\b'
                    if re.search(pattern, text, re.IGNORECASE):
                        score += 2
                else:
                    if keyword in text:
                        score += 1
            
            if score > 0:
                category_scores[category] = score
        
        if category_scores:
            # Return category with highest score
            return max(category_scores, key=category_scores.get)
        
        return MarketCategory.OTHER

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


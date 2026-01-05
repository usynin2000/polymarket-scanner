"""REST API polling transport for Polymarket trades."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal

import aiohttp

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Market, MarketCategory, Trade, TradeSide


logger = logging.getLogger(__name__)


def safe_decimal(value, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert value to Decimal."""
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


class PolymarketRESTPoller:
    """
    REST API poller for Polymarket trades.

    Uses the Polymarket CLOB API and Gamma API to fetch recent trades.
    More reliable than WebSocket for getting all trades.
    """

    CLOB_API = "https://clob.polymarket.com"
    GAMMA_API = "https://gamma-api.polymarket.com"

    def __init__(
        self,
        config: ScannerConfig | None = None,
        poll_interval: float = 5.0,
    ):
        """
        Initialize REST poller.

        Args:
            config: Scanner configuration.
            poll_interval: Seconds between polls.
        """
        self._config = config or default_config
        self._poll_interval = poll_interval
        self._running = False
        self._seen_trades: set[str] = set()
        self._markets_cache: dict[str, Market] = {}
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _fetch_markets(self) -> list[dict]:
        """Fetch active markets from Gamma API."""
        session = await self._get_session()

        try:
            url = f"{self.GAMMA_API}/markets?limit=100&active=true&closed=false"
            logger.debug(f"Fetching markets: {url}")

            async with session.get(url) as resp:
                if resp.status == 200:
                    markets = await resp.json()
                    logger.info(f"Fetched {len(markets)} markets")

                    # Cache markets
                    for market in markets:
                        condition_id = market.get("conditionId", "")
                        if condition_id:
                            self._markets_cache[condition_id] = self._parse_market(market)

                    return markets

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")

        return []

    def _parse_market(self, data: dict) -> Market:
        """Parse market data from Gamma API."""
        # Determine category from tags or question
        question = data.get("question", "").lower()
        category = MarketCategory.OTHER

        if any(w in question for w in ["election", "trump", "biden", "president", "congress"]):
            category = MarketCategory.POLITICS
        elif any(w in question for w in ["bitcoin", "ethereum", "crypto", "btc", "eth"]):
            category = MarketCategory.CRYPTO
        elif any(w in question for w in ["nfl", "nba", "soccer", "football", "game", "match"]):
            category = MarketCategory.SPORTS
        elif any(w in question for w in ["fed", "inflation", "gdp", "economy", "rate"]):
            category = MarketCategory.ECONOMICS
        elif any(w in question for w in ["ai", "spacex", "nasa", "science"]):
            category = MarketCategory.SCIENCE

        # Parse end date
        end_date = None
        end_str = data.get("endDate", "")
        if end_str:
            try:
                end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        # Get outcomes/tokens for odds
        outcomes = data.get("outcomePrices", [])
        odds_yes = Decimal("0.5")
        odds_no = Decimal("0.5")

        if len(outcomes) >= 2:
            odds_yes = safe_decimal(outcomes[0], Decimal("0.5"))
            odds_no = safe_decimal(outcomes[1], Decimal("0.5"))

        return Market(
            id=data.get("conditionId", data.get("id", "")),
            question=data.get("question", "Unknown"),
            category=category,
            end_date=end_date,
            current_odds_yes=odds_yes,
            current_odds_no=odds_no,
            volume_24h=safe_decimal(data.get("volume24hr")),
            liquidity=safe_decimal(data.get("liquidity")),
            metadata=data,
        )

    async def _fetch_trades(self, market_id: str | None = None) -> list[dict]:
        """
        Fetch recent trades from CLOB API.

        Args:
            market_id: Optional market/condition ID to filter by.

        Returns:
            List of trade dictionaries.
        """
        session = await self._get_session()

        try:
            # CLOB trades endpoint
            url = f"{self.CLOB_API}/trades"
            params = {"limit": "100"}

            if market_id:
                params["market"] = market_id

            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    trades = data if isinstance(data, list) else data.get("trades", [])
                    return trades
                else:
                    text = await resp.text()
                    logger.debug(f"Trades API returned {resp.status}: {text[:200]}")

        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")

        return []

    async def _fetch_activity(self) -> list[dict]:
        """Fetch recent activity from Gamma API."""
        session = await self._get_session()

        try:
            url = f"{self.GAMMA_API}/activity?limit=50"

            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data if isinstance(data, list) else []

        except Exception as e:
            logger.debug(f"Activity API error: {e}")

        return []

    def _parse_trade(self, data: dict) -> Trade | None:
        """Parse trade data into Trade object."""
        try:
            # Different APIs have different formats
            trade_id = (
                data.get("id")
                or data.get("transactionHash")
                or data.get("transaction_hash")
                or f"trade_{datetime.now().timestamp()}"
            )

            # Skip if already seen
            if trade_id in self._seen_trades:
                return None

            self._seen_trades.add(trade_id)

            # Keep seen trades cache manageable
            if len(self._seen_trades) > 10000:
                self._seen_trades = set(list(self._seen_trades)[-5000:])

            # Parse size and price
            size = safe_decimal(data.get("size", data.get("amount")))
            price = safe_decimal(data.get("price"), Decimal("0.5"))

            # Determine side
            side_str = str(data.get("side", data.get("outcome", ""))).upper()
            if side_str in ("BUY", "YES", "0"):
                side = TradeSide.YES
                size_usd = size * price
            else:
                side = TradeSide.NO
                size_usd = size * (1 - price)

            # Parse timestamp
            timestamp = datetime.now()
            ts_value = data.get("timestamp", data.get("createdAt", ""))
            if ts_value:
                try:
                    if isinstance(ts_value, (int, float)):
                        timestamp = datetime.fromtimestamp(ts_value)
                    elif isinstance(ts_value, str):
                        if ts_value.isdigit():
                            timestamp = datetime.fromtimestamp(int(ts_value))
                        else:
                            timestamp = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
                except (ValueError, OSError):
                    pass

            # Get wallet address
            wallet = (
                data.get("taker", "")
                or data.get("maker", "")
                or data.get("user", "")
                or data.get("proxyWallet", "")
                or "unknown"
            )

            # Get market data
            market_id = (
                data.get("market")
                or data.get("conditionId")
                or data.get("asset_id", "")
            )
            market = self._markets_cache.get(market_id)

            trade = Trade(
                id=trade_id,
                market_id=market_id,
                wallet_address=wallet,
                side=side,
                size_usd=size_usd,
                price=price,
                timestamp=timestamp,
                market=market,
                raw_data=data,
            )

            logger.info(
                f"New trade: {wallet[:10]}... {side.value} ${size_usd:.2f} @ {price:.1%}"
            )

            return trade

        except Exception as e:
            logger.debug(f"Failed to parse trade: {e}")
            return None

    async def trades(self) -> AsyncIterator[Trade]:
        """
        Poll for new trades continuously.

        Yields:
            Trade objects as they are discovered.
        """
        self._running = True

        # Initial market fetch
        await self._fetch_markets()

        logger.info(f"Starting REST poller (interval: {self._poll_interval}s)")

        while self._running:
            try:
                # Fetch from multiple sources
                all_trades = []

                # Try CLOB API (requires auth - will likely fail)
                clob_trades = await self._fetch_trades()
                if clob_trades:
                    logger.info(f"Got {len(clob_trades)} from CLOB")
                all_trades.extend(clob_trades)

                # Try Gamma activity
                activity = await self._fetch_activity()
                if activity:
                    logger.info(f"Got {len(activity)} from Gamma activity")
                all_trades.extend(activity)

                # Parse and yield new trades
                new_count = 0
                for trade_data in all_trades:
                    trade = self._parse_trade(trade_data)
                    if trade and trade.size_usd > 0:
                        new_count += 1
                        yield trade

                if new_count:
                    logger.info(f"New trades: {new_count}")

                # Periodically refresh markets
                if len(self._seen_trades) % 100 == 0:
                    await self._fetch_markets()

            except Exception as e:
                logger.error(f"Polling error: {e}")

            await asyncio.sleep(self._poll_interval)

    def stop(self) -> None:
        """Stop polling."""
        self._running = False

    async def close(self) -> None:
        """Close session."""
        if self._session:
            await self._session.close()


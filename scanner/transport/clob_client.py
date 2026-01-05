"""Polymarket CLOB client transport using py-clob-client."""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal
from typing import Any

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Market, MarketCategory, Trade, TradeSide


logger = logging.getLogger(__name__)


def safe_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """Safely convert value to Decimal."""
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


class PolymarketCLOBClient:
    """
    Polymarket CLOB client using py-clob-client.

    Requires private key for API authentication.
    Provides access to trades, orders, and market data.
    """

    def __init__(
        self,
        config: ScannerConfig | None = None,
        poll_interval: float = 3.0,
        market_refresh_interval: float = 60.0,
    ):
        """
        Initialize CLOB client.

        Args:
            config: Scanner configuration with private key.
            poll_interval: Seconds between trade polls.
            market_refresh_interval: Seconds between market cache refreshes.
        """
        self._config = config or default_config
        self._poll_interval = poll_interval
        self._market_refresh_interval = market_refresh_interval
        self._running = False
        self._seen_trades: set[str] = set()
        self._markets_cache: dict[str, Market] = {}
        self._condition_ids: set[str] = set()  # Active market condition IDs
        self._client = None
        self._last_market_refresh: float = 0
        self._session: Any = None  # Reusable aiohttp session
        self._last_trade_timestamp: int = 0  # Unix timestamp for 'after' parameter

    def _init_client(self):
        """Initialize py-clob-client with credentials."""
        if self._client is not None:
            return

        private_key = self._config.private_key
        if not private_key:
            raise ValueError(
                "Private key required for CLOB API. "
                "Set SCANNER_PRIVATE_KEY environment variable."
            )

        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds

            # Derive API credentials from private key
            host = "https://clob.polymarket.com"
            chain_id = self._config.chain_id

            # Create client and derive API key
            self._client = ClobClient(
                host=host,
                key=private_key,
                chain_id=chain_id,
            )

            # Derive API credentials
            self._client.set_api_creds(self._client.derive_api_key())

            logger.info(f"CLOB client initialized (chain_id={chain_id})")

        except ImportError:
            raise ImportError(
                "py-clob-client not installed. Run: uv pip install py-clob-client"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CLOB client: {e}")

    async def _get_session(self):
        """Get or create reusable aiohttp session."""
        import aiohttp
        
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _fetch_markets(self, retries: int = 3) -> list[dict]:
        """Fetch active markets from Gamma API with retry logic."""
        import aiohttp
        
        url = "https://gamma-api.polymarket.com/events?active=true&closed=false&limit=100"
        
        for attempt in range(retries):
            try:
                session = await self._get_session()
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(f"Gamma API error: {resp.status}")
                        if attempt < retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return []
                    events = await resp.json()
                
                if not isinstance(events, list):
                    logger.warning(f"Unexpected Gamma API response type: {type(events)}")
                    return []
                
                logger.info(f"Gamma API returned {len(events)} active events")
                break
                
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Gamma API request failed (attempt {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    # Reset session on connection errors
                    if self._session and not self._session.closed:
                        await self._session.close()
                    self._session = None
                    continue
                logger.error(f"Failed to fetch markets after {retries} attempts")
                return []
        else:
            return []
        
        # Each event can have multiple markets
        all_markets = []
        try:
            for event in events:
                if not isinstance(event, dict):
                    continue
                
                # Events contain markets array
                markets = event.get("markets", [])
                if not markets:
                    continue
                
                for market in markets:
                    if not isinstance(market, dict):
                        continue
                    
                    # Skip if not active or closed
                    if not market.get("active", True) or market.get("closed", False):
                        continue
                    
                    # Get token IDs from clobTokenIds field
                    clob_ids = market.get("clobTokenIds", [])
                    condition_id = market.get("conditionId", "")
                    
                    # Also store condition_id for live-activity API
                    if condition_id and condition_id not in self._condition_ids:
                        self._condition_ids.add(condition_id)
                    
                    # Parse and cache market by each token_id
                    parsed_market = self._parse_market(market)
                    
                    for token_id in clob_ids:
                        if token_id:
                            self._markets_cache[token_id] = parsed_market
                    
                    # Also cache by condition_id
                    if condition_id:
                        self._markets_cache[condition_id] = parsed_market
                    
                    all_markets.append(market)
            
            logger.info(f"Cached {len(self._markets_cache)} tokens from {len(all_markets)} active markets")
            
            # Log first market for debugging
            if all_markets:
                m = all_markets[0]
                logger.debug(f"Sample market: {m.get('question', 'Unknown')[:60]}...")
            
            return all_markets

        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}", exc_info=True)
            return []

    def _parse_market(self, data: dict) -> Market:
        """Parse market data from Gamma API format.
        
        Gamma API market structure:
        - conditionId: unique market ID
        - question: market question text
        - outcomes: ["Yes", "No"] or custom outcomes
        - outcomePrices: ["0.45", "0.55"] - current prices
        - volume24hr: 24h volume
        - liquidity: current liquidity
        - clobTokenIds: token IDs for trading
        - active, closed: status flags
        - groupItemTitle: category/group
        """
        question = data.get("question", "").lower()
        group_title = data.get("groupItemTitle", "").lower()
        category = MarketCategory.OTHER

        # Determine category from question or group
        text_to_check = f"{question} {group_title}"
        
        if any(w in text_to_check for w in ["election", "trump", "biden", "president", "congress", "vote", "senate", "governor"]):
            category = MarketCategory.POLITICS
        elif any(w in text_to_check for w in ["bitcoin", "ethereum", "crypto", "btc", "eth", "solana", "coin"]):
            category = MarketCategory.CRYPTO
        elif any(w in text_to_check for w in ["nfl", "nba", "mlb", "nhl", "soccer", "game", "match", "sports", "win", "score", "championship", "playoff"]):
            category = MarketCategory.SPORTS
        elif any(w in text_to_check for w in ["fed", "inflation", "gdp", "economy", "rate", "jobs", "unemployment", "cpi"]):
            category = MarketCategory.ECONOMICS

        # Parse odds from outcomePrices (Gamma API format)
        odds_yes = Decimal("0.5")
        odds_no = Decimal("0.5")
        
        # outcomePrices is a JSON string in Gamma API: "[\"0.45\", \"0.55\"]"
        outcome_prices = data.get("outcomePrices", [])
        
        # Handle if it's a string (JSON)
        if isinstance(outcome_prices, str):
            try:
                import json
                outcome_prices = json.loads(outcome_prices)
            except Exception:
                outcome_prices = []
        
        if outcome_prices and len(outcome_prices) >= 2:
            odds_yes = safe_decimal(outcome_prices[0], Decimal("0.5"))
            odds_no = safe_decimal(outcome_prices[1], Decimal("0.5"))
        else:
            # Fallback to CLOB API format with tokens
            tokens = data.get("tokens", [])
            for token in tokens:
                if isinstance(token, dict):
                    outcome = token.get("outcome", "")
                    price = safe_decimal(token.get("price"), Decimal("0.5"))
                    if outcome == "Yes":
                        odds_yes = price
                    elif outcome == "No":
                        odds_no = price

        # Parse volume (can be string or number)
        volume_24h = safe_decimal(data.get("volume24hr", data.get("volume")))
        liquidity = safe_decimal(data.get("liquidity"))

        return Market(
            id=data.get("conditionId", data.get("condition_id", "")),
            question=data.get("question", "Unknown"),
            category=category,
            current_odds_yes=odds_yes,
            current_odds_no=odds_no,
            volume_24h=volume_24h,
            liquidity=liquidity,
            metadata=data,
        )

    async def _fetch_trades(self) -> list[dict]:
        """Fetch recent trades using Data API /trades endpoint.
        
        Uses 'after' parameter to fetch only trades newer than last poll,
        reducing bandwidth and simplifying deduplication.
        
        Response fields:
        - proxyWallet: trader's wallet address
        - side: "BUY" or "SELL"
        - asset: token_id
        - conditionId: market condition_id
        - size: trade size in tokens
        - price: execution price (0-1)
        - timestamp: unix timestamp
        - title: market question
        - transactionHash: unique trade identifier
        """
        import aiohttp
        import time
        
        try:
            session = await self._get_session()
            
            # Use 'after' parameter to get only new trades since last poll
            # This reduces response size and simplifies deduplication
            url = "https://data-api.polymarket.com/trades?limit=200"
            
            if self._last_trade_timestamp > 0:
                # Add 'after' parameter to fetch only newer trades
                url += f"&after={self._last_trade_timestamp}"
                logger.debug(f"Fetching trades after timestamp {self._last_trade_timestamp}")
            
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.error(f"Data API error: {resp.status}")
                        return []
                    
                    trades = await resp.json()
                    
                    if not trades or not isinstance(trades, list):
                        logger.debug("No trades from Data API")
                        return []
                    
                    # Update last timestamp from newest trade
                    max_timestamp = self._last_trade_timestamp
                    for trade in trades:
                        if isinstance(trade, dict):
                            ts = trade.get("timestamp", 0)
                            if isinstance(ts, (int, float)) and ts > max_timestamp:
                                max_timestamp = int(ts)
                    
                    if max_timestamp > self._last_trade_timestamp:
                        self._last_trade_timestamp = max_timestamp
                        logger.debug(f"Updated last_trade_timestamp to {max_timestamp}")
                    
                    # Normalize field names
                    all_trades = []
                    for trade in trades:
                        if isinstance(trade, dict):
                            trade["condition_id"] = trade.get("conditionId", "")
                            trade["token_id"] = trade.get("asset", "")
                            trade["maker"] = trade.get("proxyWallet", "unknown")
                            all_trades.append(trade)
                    
                    logger.debug(f"Fetched {len(all_trades)} trades from Data API (after={self._last_trade_timestamp})")
                    
                    return all_trades
                                        
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Error fetching trades: {e}")
                return []

        except Exception as e:
            logger.error(f"Failed to fetch trades: {e}")
            return []

    def _parse_trade(self, data: dict) -> Trade | None:
        """Parse trade data from Data API /trades response.
        
        Data API trade format:
        - proxyWallet: trader's wallet address
        - side: "BUY" or "SELL"
        - asset: token_id
        - conditionId: market condition_id
        - size: trade size in tokens (float)
        - price: execution price 0-1 (float)
        - timestamp: unix timestamp (seconds)
        - title: market question
        - slug: market URL slug
        - transactionHash: unique blockchain transaction hash
        """
        try:
            # Use transactionHash as unique trade ID (most reliable)
            trade_id = data.get("transactionHash", "")
            
            # Fallback if no transactionHash
            if not trade_id:
                ts = data.get("timestamp", 0)
                wallet = data.get("proxyWallet", data.get("maker", ""))
                asset = data.get("asset", data.get("token_id", ""))
                size = data.get("size", 0)
                trade_id = f"{wallet}_{asset}_{ts}_{size}"

            if trade_id in self._seen_trades:
                return None

            self._seen_trades.add(trade_id)

            # Keep cache manageable (smaller now since 'after' param handles most filtering)
            if len(self._seen_trades) > 2000:
                self._seen_trades = set(list(self._seen_trades)[-1000:])

            # Parse fields
            size = safe_decimal(data.get("size", 0))
            price = safe_decimal(data.get("price"), Decimal("0.5"))

            # Determine side - Data API uses BUY/SELL
            side_str = str(data.get("side", "")).upper()
            if side_str == "BUY":
                side = TradeSide.YES
                # For BUY YES tokens: USD value = size * price
                size_usd = size * price
            else:
                side = TradeSide.NO
                # For SELL (buy NO): USD value = size * (1 - price)
                size_usd = size * (Decimal("1") - price)

            # Parse timestamp (Data API returns seconds, not milliseconds)
            timestamp = datetime.now()
            ts_value = data.get("timestamp")
            if ts_value:
                try:
                    if isinstance(ts_value, (int, float)):
                        # Data API uses seconds, check if it looks like ms
                        if ts_value > 1000000000000:
                            timestamp = datetime.fromtimestamp(ts_value / 1000)
                        else:
                            timestamp = datetime.fromtimestamp(ts_value)
                    elif isinstance(ts_value, str):
                        if ts_value.replace(".", "").isdigit():
                            ts_float = float(ts_value)
                            if ts_float > 1000000000000:
                                timestamp = datetime.fromtimestamp(ts_float / 1000)
                            else:
                                timestamp = datetime.fromtimestamp(ts_float)
                        else:
                            timestamp = datetime.fromisoformat(
                                ts_value.replace("Z", "+00:00")
                            )
                except (ValueError, OSError) as e:
                    logger.debug(f"Failed to parse timestamp {ts_value}: {e}")

            # Get wallet address from proxyWallet field
            wallet = data.get("proxyWallet", data.get("maker", "unknown"))
            
            # Get market ID
            condition_id = data.get("conditionId", data.get("condition_id", ""))
            asset_id = data.get("asset", data.get("token_id", ""))
            market_id = condition_id or asset_id
            
            # Try to find market in cache
            market = self._markets_cache.get(condition_id) or self._markets_cache.get(asset_id)

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

            # Log trade (show question if available)
            question = data.get("title", market.question if market else "Unknown")[:40]
            logger.info(
                f"Trade: {wallet[:8]}... {side.value} ${size_usd:.2f} @ {price:.3f} | {question}..."
            )

            return trade

        except Exception as e:
            logger.debug(f"Failed to parse trade: {e}", exc_info=True)
            return None

    async def trades(self) -> AsyncIterator[Trade]:
        """
        Poll for new trades.

        Yields:
            Trade objects.
        """
        import time
        
        self._running = True

        # Initialize client
        self._init_client()

        # Fetch initial markets
        await self._fetch_markets()
        self._last_market_refresh = time.time()

        logger.info(f"CLOB client polling (interval: {self._poll_interval}s, market refresh: {self._market_refresh_interval}s)")

        try:
            while self._running:
                try:
                    trades = await self._fetch_trades()
                    new_trades_count = 0

                    for trade_data in trades:
                        trade = self._parse_trade(trade_data)
                        if trade and trade.size_usd > 0:
                            new_trades_count += 1
                            yield trade

                    if new_trades_count > 0:
                        logger.info(f"Found {new_trades_count} new trades this poll")
                    else:
                        logger.debug(f"No new trades (seen {len(self._seen_trades)} unique)")

                    # Refresh markets periodically by time
                    current_time = time.time()
                    if current_time - self._last_market_refresh > self._market_refresh_interval:
                        logger.debug("Refreshing market cache...")
                        await self._fetch_markets()
                        self._last_market_refresh = current_time

                except Exception as e:
                    logger.error(f"Polling error: {e}")

                await asyncio.sleep(self._poll_interval)
        finally:
            await self._close_session()

    async def _close_session(self) -> None:
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def stop(self) -> None:
        """Stop polling."""
        self._running = False


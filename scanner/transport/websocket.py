"""Polymarket WebSocket transport."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Trade, TradeSide


logger = logging.getLogger(__name__)


class PolymarketWebSocket:
    """
    WebSocket connection to Polymarket CLOB.

    Connects to the market WebSocket feed to receive trades in real-time.
    First fetches active markets via REST API, then subscribes to WebSocket.

    Handles:
    - Connection management
    - Automatic reconnection
    - Message parsing into Trade objects
    """

    # Polymarket API endpoints
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    REST_API = "https://clob.polymarket.com"
    GAMMA_API = "https://gamma-api.polymarket.com"

    def __init__(self, config: ScannerConfig | None = None):
        """
        Initialize WebSocket transport.

        Args:
            config: Scanner configuration.
        """
        self._config = config or default_config
        self._ws = None
        self._running = False
        self._subscribed_assets: set[str] = set()
        self._asset_to_market: dict[str, dict] = {}

    async def _fetch_active_markets(self, limit: int = 100) -> list[str]:
        """
        Fetch active market asset IDs from Polymarket REST API.

        Args:
            limit: Maximum number of markets to fetch.

        Returns:
            List of asset IDs (condition token IDs).
        """
        asset_ids = []

        async with aiohttp.ClientSession() as session:
            try:
                # Try CLOB API first
                url = f"{self.REST_API}/markets?limit={limit}&active=true"
                logger.info(f"Fetching active markets from {url}")

                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # CLOB API returns markets with tokens
                        for market in data:
                            if isinstance(market, dict):
                                # Extract token IDs (assets)
                                tokens = market.get("tokens", [])
                                for token in tokens:
                                    token_id = token.get("token_id")
                                    if token_id:
                                        asset_ids.append(token_id)
                                        self._asset_to_market[token_id] = market

                        logger.info(f"Found {len(asset_ids)} asset IDs from CLOB API")

            except Exception as e:
                logger.warning(f"CLOB API failed: {e}")

            # If no assets found, try Gamma API
            if not asset_ids:
                try:
                    url = f"{self.GAMMA_API}/markets?limit={limit}&active=true&closed=false"
                    logger.info(f"Trying Gamma API: {url}")

                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            for market in data:
                                if isinstance(market, dict):
                                    clob_ids = market.get("clobTokenIds", [])
                                    for token_id in clob_ids:
                                        if token_id:
                                            asset_ids.append(token_id)
                                            self._asset_to_market[token_id] = market

                            logger.info(f"Found {len(asset_ids)} asset IDs from Gamma API")

                except Exception as e:
                    logger.error(f"Gamma API also failed: {e}")

        return asset_ids[:limit]

    async def connect(self) -> None:
        """Establish WebSocket connection."""
        url = self._config.ws_url or self.WS_URL
        logger.info(f"Connecting to {url}")

        self._ws = await websockets.connect(
            url,
            ping_interval=self._config.ws_ping_interval,
            ping_timeout=60,
            close_timeout=10,
        )
        self._running = True
        logger.info("WebSocket connected")

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._running = False

        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.info("WebSocket disconnected")

    async def subscribe(self, asset_ids: list[str] | None = None) -> None:
        """
        Subscribe to market updates.

        Args:
            asset_ids: Specific asset IDs to subscribe to. If None, fetches active markets.
        """
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        # If no asset IDs provided, fetch active markets
        if not asset_ids:
            asset_ids = await self._fetch_active_markets(limit=50)

        if not asset_ids:
            logger.warning("No asset IDs to subscribe to!")
            return

        # Polymarket subscription format for /ws/market
        subscription = {
            "type": "subscribe",
            "channel": "market",
            "assets_ids": asset_ids,
        }

        await self._ws.send(json.dumps(subscription))
        self._subscribed_assets.update(asset_ids)

        logger.info(f"Subscribed to {len(asset_ids)} assets")

    async def trades(self) -> AsyncIterator[Trade]:
        """
        Iterate over incoming trades.

        Yields:
            Trade objects parsed from WebSocket messages.
        """
        # Connect and subscribe
        await self.connect()
        await self.subscribe()

        while self._running:
            try:
                if not self._ws:
                    await self._reconnect()
                    continue

                message = await self._ws.recv()
                # Log raw messages for debugging
                logger.info(f"WS message: {message[:300]}...")
                trade = self._parse_message(message)

                if trade:
                    yield trade

            except ConnectionClosed:
                logger.warning("WebSocket connection closed, reconnecting...")
                await self._reconnect()

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {e}")

            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)

    async def _reconnect(self) -> None:
        """Handle reconnection with backoff."""
        self._ws = None

        logger.info(f"Reconnecting in {self._config.ws_reconnect_delay}s...")
        await asyncio.sleep(self._config.ws_reconnect_delay)

        try:
            await self.connect()
            await self.subscribe(list(self._subscribed_assets) if self._subscribed_assets else None)

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")

    def _parse_message(self, message: str) -> Trade | None:
        """
        Parse WebSocket message into Trade object.

        Polymarket market WebSocket message formats:
        
        Trade event:
        {
            "event_type": "trade" | "last_trade_price",
            "asset_id": "...",
            "market": "...",
            "side": "BUY" | "SELL", 
            "size": "100.5",
            "price": "0.55",
            "maker_address": "0x...",
            "taker_address": "0x...",
            "transaction_hash": "0x...",
            "timestamp": "1704067200"
        }

        Price update:
        {
            "event_type": "price_change",
            "asset_id": "...",
            "price": "0.55",
            ...
        }

        Args:
            message: Raw WebSocket message.

        Returns:
            Trade object or None if message is not a trade.
        """
        try:
            data = json.loads(message)

            # Handle array of events
            if isinstance(data, list):
                # Process first trade event in array
                for event in data:
                    trade = self._parse_event(event)
                    if trade:
                        return trade
                return None

            return self._parse_event(data)

        except Exception as e:
            logger.debug(f"Failed to parse message: {e}")
            return None

    def _parse_event(self, data: dict) -> Trade | None:
        """Parse a single event dict into a Trade."""
        try:
            event_type = data.get("event_type", "")

            # Only process trade events
            if event_type not in ("trade", "last_trade_price"):
                return None

            # Parse trade data
            size = Decimal(str(data.get("size", "0")))
            price = Decimal(str(data.get("price", "0.5")))

            # Determine side: BUY = YES, SELL = NO
            side_str = data.get("side", "").upper()
            if side_str == "BUY":
                side = TradeSide.YES
                size_usd = size * price
            else:
                side = TradeSide.NO
                size_usd = size * (1 - price)

            # Parse timestamp
            timestamp_str = data.get("timestamp", "")
            if timestamp_str:
                try:
                    timestamp = datetime.fromtimestamp(int(timestamp_str))
                except (ValueError, OSError):
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()

            # Get wallet address
            wallet = data.get("taker_address") or data.get("maker_address") or "unknown"

            # Get market info if available
            asset_id = data.get("asset_id", "")
            market_info = self._asset_to_market.get(asset_id, {})

            trade = Trade(
                id=data.get("transaction_hash", f"trade_{timestamp.timestamp()}"),
                market_id=data.get("market", asset_id),
                wallet_address=wallet,
                side=side,
                size_usd=size_usd,
                price=price,
                timestamp=timestamp,
                raw_data={**data, "market_info": market_info},
            )

            logger.debug(
                f"Trade: {wallet[:10]}... {side.value} ${size_usd:.2f} @ {price:.2%}"
            )

            return trade

        except Exception as e:
            logger.debug(f"Failed to parse event: {e}")
            return None

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and self._running

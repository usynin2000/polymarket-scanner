"""Mock trade generator for testing."""

import asyncio
import random
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from decimal import Decimal

from scanner.domain.models import Market, MarketCategory, Trade, TradeSide


# Sample market questions for realistic mock data
SAMPLE_QUESTIONS = [
    "Will AI surpass human-level reasoning by 2030?",
    "Will the Fed cut rates in Q1 2026?",
    "Will there be a major cyber attack on US infrastructure?",
    "Will renewable energy exceed 50% of US power generation?",
    "Will a new pandemic emerge requiring lockdowns?",
    "Will inflation drop below 2% in 2026?",
    "Will Democrats win the 2028 presidential election?",
    "Will Tesla stock exceed $500 by end of 2026?",
    "Will there be a government shutdown in 2026?",
    "Will autonomous vehicles be approved for widespread use?",
]

# Sample wallet addresses (mock)
SAMPLE_WALLETS = [
    "0x742d35Cc6634C0532925a3b844Bc9e7595f8fE10",
    "0x8ba1f109551bD432803012645Ac136ddd64DBa72",
    "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
    "0x1234567890abcdef1234567890abcdef12345678",
    "0xDEADBEEF0000000000000000000000000000CAFE",
    "0xFreshWallet00000000000000000000000000001",
    "0xFreshWallet00000000000000000000000000002",
    "0xWhale0000000000000000000000000000000001",
]


class MockTradeGenerator:
    """
    Mock trade generator for testing without real WebSocket.

    Generates realistic-looking trades with configurable parameters.
    """

    def __init__(
        self,
        trades_per_minute: float = 10,
        min_size: Decimal = Decimal("100"),
        max_size: Decimal = Decimal("50000"),
        large_trade_probability: float = 0.1,
    ):
        """
        Initialize mock generator.

        Args:
            trades_per_minute: Average trade frequency.
            min_size: Minimum trade size in USD.
            max_size: Maximum trade size in USD.
            large_trade_probability: Chance of generating large ($5k+) trades.
        """
        self._rate = trades_per_minute
        self._min_size = min_size
        self._max_size = max_size
        self._large_prob = large_trade_probability
        self._running = False
        self._markets: dict[str, Market] = {}

        # Pre-generate some markets
        self._generate_markets()

    def _generate_markets(self) -> None:
        """Generate mock markets."""
        categories = [
            MarketCategory.POLITICS,
            MarketCategory.ECONOMICS,
            MarketCategory.SCIENCE,
            MarketCategory.ENTERTAINMENT,
            MarketCategory.OTHER,
        ]

        for i, question in enumerate(SAMPLE_QUESTIONS):
            market_id = f"market_{uuid.uuid4().hex[:8]}"
            odds_yes = Decimal(str(random.randint(20, 80))) / 100

            self._markets[market_id] = Market(
                id=market_id,
                question=question,
                category=random.choice(categories),
                current_odds_yes=odds_yes,
                current_odds_no=1 - odds_yes,
                volume_24h=Decimal(str(random.randint(10000, 500000))),
                liquidity=Decimal(str(random.randint(50000, 300000))),
            )

    def _generate_trade(self) -> Trade:
        """Generate a single mock trade."""
        market = random.choice(list(self._markets.values()))

        # Determine trade size
        if random.random() < self._large_prob:
            # Large trade
            size = Decimal(str(random.randint(5000, int(self._max_size))))
        else:
            # Normal trade
            size = Decimal(str(random.randint(int(self._min_size), 5000)))

        # Choose wallet - bias towards fresh wallets occasionally
        if random.random() < 0.2:
            wallet = random.choice(SAMPLE_WALLETS[-3:])  # Fresh/whale wallets
        else:
            wallet = random.choice(SAMPLE_WALLETS[:-3])

        # Determine side - slight bias based on current odds
        if random.random() < float(market.current_odds_yes):
            side = TradeSide.YES
            price = market.current_odds_yes
        else:
            side = TradeSide.NO
            price = market.current_odds_no

        return Trade(
            id=f"trade_{uuid.uuid4().hex[:12]}",
            market_id=market.id,
            wallet_address=wallet,
            side=side,
            size_usd=size,
            price=price,
            timestamp=datetime.now(),
            market=market,
        )

    async def trades(self) -> AsyncIterator[Trade]:
        """
        Generate mock trades at configured rate.

        Yields:
            Mock Trade objects.
        """
        self._running = True
        interval = 60.0 / self._rate  # Seconds between trades

        while self._running:
            # Add some randomness to timing
            jitter = random.uniform(0.5, 1.5)
            await asyncio.sleep(interval * jitter)

            trade = self._generate_trade()
            yield trade

    def stop(self) -> None:
        """Stop generating trades."""
        self._running = False

    def get_market(self, market_id: str) -> Market | None:
        """Get a mock market by ID."""
        return self._markets.get(market_id)


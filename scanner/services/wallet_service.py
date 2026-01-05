"""Wallet profile service."""

from datetime import datetime
from decimal import Decimal

from scanner.domain.models import WalletProfile


class WalletService:
    """
    Service for fetching and caching wallet profiles.

    TODO: Replace mock implementation with real Polymarket/blockchain API calls.
    """

    def __init__(self):
        """Initialize wallet service."""
        # In-memory cache for wallet profiles
        self._cache: dict[str, WalletProfile] = {}

    async def get_profile(self, wallet_address: str) -> WalletProfile:
        """
        Get wallet profile, fetching from API if not cached.

        Args:
            wallet_address: Wallet address to lookup.

        Returns:
            WalletProfile with historical data.
        """
        if wallet_address in self._cache:
            return self._cache[wallet_address]

        # TODO: Fetch real data from Polymarket API or blockchain
        # For now, return a mock profile
        profile = await self._fetch_profile(wallet_address)
        self._cache[wallet_address] = profile

        return profile

    async def _fetch_profile(self, wallet_address: str) -> WalletProfile:
        """
        Fetch wallet profile from external API.

        TODO: Implement real API call to:
        - Polymarket subgraph
        - Polygon blockchain
        - Internal database

        Args:
            wallet_address: Wallet to fetch.

        Returns:
            WalletProfile with fetched data.
        """
        # MOCK: Generate profile based on address
        # In production, this would be a real API call

        # Use address hash to create deterministic mock data
        addr_hash = hash(wallet_address)

        # Simulate different wallet types
        is_fresh = (addr_hash % 10) < 3  # 30% chance of fresh wallet
        is_whale = (addr_hash % 20) == 0  # 5% chance of whale

        if is_fresh:
            return WalletProfile(
                address=wallet_address,
                total_trades=addr_hash % 5,
                total_volume_usd=Decimal(str(addr_hash % 10000)),
                win_rate=Decimal("0.5"),
                avg_trade_size=Decimal(str(500 + (addr_hash % 2000))),
                first_seen=datetime.now(),
                last_seen=datetime.now(),
                is_suspected_lp=False,
            )

        if is_whale:
            return WalletProfile(
                address=wallet_address,
                total_trades=100 + (addr_hash % 500),
                total_volume_usd=Decimal(str(1000000 + (addr_hash % 5000000))),
                win_rate=Decimal(str(0.5 + (addr_hash % 30) / 100)),
                avg_trade_size=Decimal(str(10000 + (addr_hash % 50000))),
                first_seen=datetime(2023, 1, 1),
                last_seen=datetime.now(),
                is_suspected_lp=False,
            )

        # Regular trader
        return WalletProfile(
            address=wallet_address,
            total_trades=10 + (addr_hash % 100),
            total_volume_usd=Decimal(str(10000 + (addr_hash % 100000))),
            win_rate=Decimal(str(0.4 + (addr_hash % 20) / 100)),
            avg_trade_size=Decimal(str(1000 + (addr_hash % 5000))),
            first_seen=datetime(2024, 1, 1),
            last_seen=datetime.now(),
            is_suspected_lp=(addr_hash % 15) == 0,
        )

    async def update_profile(self, wallet_address: str, trade_size: Decimal) -> None:
        """
        Update wallet profile after a trade.

        Args:
            wallet_address: Wallet that traded.
            trade_size: Size of the trade in USD.
        """
        if wallet_address not in self._cache:
            await self.get_profile(wallet_address)

        profile = self._cache[wallet_address]

        # Update statistics
        new_total = profile.total_trades + 1
        new_volume = profile.total_volume_usd + trade_size
        new_avg = new_volume / Decimal(str(new_total))

        self._cache[wallet_address] = WalletProfile(
            address=wallet_address,
            total_trades=new_total,
            total_volume_usd=new_volume,
            win_rate=profile.win_rate,
            avg_trade_size=new_avg,
            first_seen=profile.first_seen,
            last_seen=datetime.now(),
            preferred_categories=profile.preferred_categories,
            is_suspected_lp=profile.is_suspected_lp,
        )

    def clear_cache(self) -> None:
        """Clear wallet profile cache."""
        self._cache.clear()


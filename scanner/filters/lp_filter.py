"""Liquidity Provider detection filter."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Trade, TradeSide
from scanner.filters.base import FilterResult, TradeFilter


@dataclass
class WalletTradeHistory:
    """Track recent trades for a wallet."""

    trades: list[tuple[datetime, TradeSide, Decimal]] = field(default_factory=list)
    yes_volume: Decimal = Decimal("0")
    no_volume: Decimal = Decimal("0")

    def add_trade(self, timestamp: datetime, side: TradeSide, size: Decimal) -> None:
        """Add a trade to history."""
        self.trades.append((timestamp, side, size))
        if side == TradeSide.YES:
            self.yes_volume += size
        else:
            self.no_volume += size

    def get_balance_ratio(self) -> Decimal:
        """
        Calculate balance ratio between YES and NO positions.

        Returns 0 if perfectly balanced, 1 if completely one-sided.
        """
        total = self.yes_volume + self.no_volume
        if total == 0:
            return Decimal("1")

        yes_ratio = self.yes_volume / total
        # Distance from 0.5 (perfect balance), normalized to 0-1
        return abs(yes_ratio - Decimal("0.5")) * 2

    def is_repetitive(self, window_size: int) -> bool:
        """
        Check for repetitive symmetric trading pattern.

        Args:
            window_size: Number of recent trades to analyze.

        Returns:
            True if pattern suggests LP behavior.
        """
        if len(self.trades) < window_size:
            return False

        recent = self.trades[-window_size:]

        # Count alternating trades
        alternating_count = 0
        for i in range(1, len(recent)):
            if recent[i][1] != recent[i - 1][1]:
                alternating_count += 1

        # If most trades alternate, likely LP
        return alternating_count >= (window_size - 1) * 0.7

    def cleanup_old(self, max_age: timedelta) -> None:
        """Remove trades older than max_age."""
        cutoff = datetime.now() - max_age
        self.trades = [t for t in self.trades if t[0] >= cutoff]

        # Recalculate volumes
        self.yes_volume = sum(
            t[2] for t in self.trades if t[1] == TradeSide.YES
        )
        self.no_volume = sum(
            t[2] for t in self.trades if t[1] == TradeSide.NO
        )


class LPFilter(TradeFilter):
    """
    Filter to detect and exclude Liquidity Provider trades.

    Uses heuristics:
    - Balanced YES/NO positions
    - Repetitive symmetric trading patterns
    """

    def __init__(self, config: ScannerConfig | None = None):
        """
        Initialize LP filter.

        Args:
            config: Scanner configuration.
        """
        self._config = config or default_config
        self._balance_threshold = self._config.lp_balance_threshold
        self._repetition_window = self._config.lp_repetition_window
        self._wallet_history: dict[str, WalletTradeHistory] = defaultdict(WalletTradeHistory)

    @property
    def name(self) -> str:
        """Filter name."""
        return "LPFilter"

    async def check(self, trade: Trade) -> FilterResult:
        """
        Check if trade appears to be from a liquidity provider.

        Args:
            trade: Trade to check.

        Returns:
            FilterResult - rejected if trade looks like LP activity.
        """
        wallet = trade.wallet_address
        history = self._wallet_history[wallet]

        # Cleanup old trades (keep last 24 hours)
        history.cleanup_old(timedelta(hours=24))

        # Add current trade to history
        history.add_trade(trade.timestamp, trade.side, trade.size_usd)

        # Check for balanced positions
        balance_ratio = history.get_balance_ratio()
        if balance_ratio < self._balance_threshold:
            return FilterResult.reject(
                f"Balanced positions detected (ratio: {balance_ratio:.2f})"
            )

        # Check for repetitive patterns
        if history.is_repetitive(self._repetition_window):
            return FilterResult.reject("Repetitive symmetric trading pattern detected")

        return FilterResult.accept()

    def clear_history(self) -> None:
        """Clear all wallet histories."""
        self._wallet_history.clear()


"""Trade clustering detector."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Signal, SignalType, Trade, TradeSide, WalletProfile
from scanner.signals.base import SignalDetector


@dataclass
class ClusterTrade:
    """Trade in a cluster."""

    wallet: str
    side: TradeSide
    size: Decimal
    timestamp: datetime


class ClusteringDetector(SignalDetector):
    """
    Detect trade clustering - multiple wallets trading same direction
    in a short time window.

    This can indicate coordinated activity or information spreading.
    """

    def __init__(self, config: ScannerConfig | None = None):
        """
        Initialize detector.

        Args:
            config: Scanner configuration.
        """
        self._config = config or default_config
        self._time_window = timedelta(seconds=self._config.clustering_time_window)
        self._min_trades = self._config.clustering_min_trades

        # Track recent trades per market: market_id -> list of cluster trades
        self._recent_trades: dict[str, list[ClusterTrade]] = defaultdict(list)

    @property
    def name(self) -> str:
        """Detector name."""
        return "ClusteringDetector"

    def _cleanup_old_trades(self, market_id: str, current_time: datetime) -> None:
        """Remove trades outside the time window."""
        cutoff = current_time - self._time_window
        self._recent_trades[market_id] = [
            t for t in self._recent_trades[market_id] if t.timestamp >= cutoff
        ]

    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        """
        Check if trade is part of a cluster.

        Args:
            trade: Trade to analyze.
            wallet_profile: Not used currently.

        Returns:
            TradeClustering signal if cluster detected.
        """
        market_id = trade.market_id

        # Cleanup old trades
        self._cleanup_old_trades(market_id, trade.timestamp)

        # Add current trade
        cluster_trade = ClusterTrade(
            wallet=trade.wallet_address,
            side=trade.side,
            size=trade.size_usd,
            timestamp=trade.timestamp,
        )
        self._recent_trades[market_id].append(cluster_trade)

        # Get unique wallets trading same direction
        same_side = [
            t for t in self._recent_trades[market_id]
            if t.side == trade.side
        ]

        unique_wallets = set(t.wallet for t in same_side)
        total_volume = sum(t.size for t in same_side)

        if len(unique_wallets) >= self._min_trades:
            # Cluster detected!
            time_span = (same_side[-1].timestamp - same_side[0].timestamp).seconds

            confidence = Decimal("0.6") + (
                Decimal(str(len(unique_wallets))) * Decimal("0.1")
            )

            return Signal(
                type=SignalType.TRADE_CLUSTERING,
                confidence=min(confidence, Decimal("0.95")),
                description=(
                    f"{len(unique_wallets)} wallets traded {trade.side.value} "
                    f"(${total_volume:,.0f}) in {time_span}s"
                ),
                metadata={
                    "unique_wallets": len(unique_wallets),
                    "total_volume": float(total_volume),
                    "time_span_seconds": time_span,
                    "side": trade.side.value,
                },
            )

        return None

    def clear_history(self) -> None:
        """Clear trade history."""
        self._recent_trades.clear()


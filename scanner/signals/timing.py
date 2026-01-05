"""Timing-based signal detector."""

from datetime import datetime, timedelta
from decimal import Decimal

from scanner.domain.models import Signal, SignalType, Trade, WalletProfile
from scanner.signals.base import SignalDetector


class TimingDetector(SignalDetector):
    """
    Detect timing-based signals:
    - Trades during unusual hours
    - Trades close to market resolution
    - Trades immediately after major events
    """

    # UTC hours considered "off-peak" for US markets
    OFF_PEAK_HOURS = set(range(0, 6)) | set(range(11, 14))  # 0-6 and 11-14 UTC

    def __init__(self):
        """Initialize detector."""
        # TODO: Could track event timestamps for correlation

    @property
    def name(self) -> str:
        """Detector name."""
        return "TimingDetector"

    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        """
        Check for timing-based signals.

        Args:
            trade: Trade to analyze.
            wallet_profile: Not used currently.

        Returns:
            TimingSignal if timing is notable.
        """
        now = trade.timestamp
        signals_found: list[str] = []
        confidence = Decimal("0.5")

        # Check for off-peak trading
        if now.hour in self.OFF_PEAK_HOURS:
            signals_found.append("off-peak hours")
            confidence += Decimal("0.1")

        # Check if market is close to resolution
        if trade.market and trade.market.end_date:
            time_to_end = trade.market.end_date - now

            if timedelta(0) < time_to_end <= timedelta(hours=24):
                signals_found.append("within 24h of resolution")
                confidence += Decimal("0.2")
            elif timedelta(0) < time_to_end <= timedelta(hours=1):
                signals_found.append("within 1h of resolution")
                confidence += Decimal("0.3")

        # Weekend trading (markets typically quieter)
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            signals_found.append("weekend trading")
            confidence += Decimal("0.1")

        if signals_found:
            return Signal(
                type=SignalType.TIMING_SIGNAL,
                confidence=min(confidence, Decimal("0.95")),
                description=f"Timing factors: {', '.join(signals_found)}",
                metadata={
                    "hour_utc": now.hour,
                    "day_of_week": now.strftime("%A"),
                    "factors": signals_found,
                },
            )

        return None


"""Odds movement correlation detector."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from scanner.domain.models import Signal, SignalType, Trade, TradeSide, WalletProfile
from scanner.signals.base import SignalDetector


@dataclass
class OddsSnapshot:
    """Snapshot of market odds at a point in time."""

    timestamp: datetime
    odds_yes: Decimal
    odds_no: Decimal


class OddsMovementDetector(SignalDetector):
    """
    Detect trades that correlate with significant odds movements.

    Tracks:
    - Trades that precede large odds changes
    - Trades during unusual volatility
    """

    def __init__(self, lookback_minutes: int = 5):
        """
        Initialize detector.

        Args:
            lookback_minutes: Minutes of odds history to track.
        """
        self._lookback = timedelta(minutes=lookback_minutes)
        self._odds_history: dict[str, list[OddsSnapshot]] = defaultdict(list)

    @property
    def name(self) -> str:
        """Detector name."""
        return "OddsMovementDetector"

    def record_odds(self, market_id: str, odds_yes: Decimal, odds_no: Decimal) -> None:
        """
        Record current odds for a market.

        Should be called periodically to track odds changes.
        """
        self._odds_history[market_id].append(
            OddsSnapshot(
                timestamp=datetime.now(),
                odds_yes=odds_yes,
                odds_no=odds_no,
            )
        )

        # Cleanup old snapshots
        cutoff = datetime.now() - self._lookback * 2
        self._odds_history[market_id] = [
            s for s in self._odds_history[market_id] if s.timestamp >= cutoff
        ]

    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        """
        Check if trade correlates with odds movement.

        Args:
            trade: Trade to analyze.
            wallet_profile: Not used currently.

        Returns:
            OddsMovement signal if correlation detected.
        """
        if trade.market is None:
            return None

        market_id = trade.market_id
        history = self._odds_history.get(market_id, [])

        if len(history) < 2:
            # Not enough history
            return None

        # Get odds from lookback period
        cutoff = trade.timestamp - self._lookback
        recent = [s for s in history if s.timestamp >= cutoff]

        if not recent:
            return None

        # Calculate odds movement
        first_odds = recent[0].odds_yes
        current_odds = trade.market.current_odds_yes
        movement = abs(current_odds - first_odds)

        # Significant movement threshold (e.g., 5% change)
        if movement >= Decimal("0.05"):
            # Check if trade direction aligns with movement
            odds_going_up = current_odds > first_odds
            trade_is_yes = trade.side == TradeSide.YES

            aligned = odds_going_up == trade_is_yes

            return Signal(
                type=SignalType.ODDS_MOVEMENT,
                confidence=Decimal("0.7") + (movement * 2),
                description=(
                    f"Odds moved {movement:.1%} in {self._lookback.seconds // 60}min, "
                    f"trade {'aligned' if aligned else 'contrary'}"
                ),
                metadata={
                    "odds_change": float(movement),
                    "aligned": aligned,
                    "initial_odds": float(first_odds),
                    "current_odds": float(current_odds),
                },
            )

        return None


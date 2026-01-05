"""Contrarian behavior detector."""

from decimal import Decimal

from scanner.domain.models import Signal, SignalType, Trade, TradeSide, WalletProfile
from scanner.signals.base import SignalDetector


class ContrarianDetector(SignalDetector):
    """
    Detect contrarian trading behavior.

    Flags trades that go against:
    - Current market consensus (low odds side)
    - Recent market trend
    """

    # Threshold for considering a position "contrarian"
    CONTRARIAN_THRESHOLD = Decimal("0.25")  # Betting on <25% odds

    def __init__(self):
        """Initialize detector."""

    @property
    def name(self) -> str:
        """Detector name."""
        return "ContrarianDetector"

    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        """
        Check if trade is contrarian.

        Args:
            trade: Trade to analyze.
            wallet_profile: Not used currently.

        Returns:
            Contrarian signal if trade goes against consensus.
        """
        if trade.market is None:
            return None

        # Get odds for the side being traded
        if trade.side == TradeSide.YES:
            odds = trade.market.current_odds_yes
            opposite_odds = trade.market.current_odds_no
        else:
            odds = trade.market.current_odds_no
            opposite_odds = trade.market.current_odds_yes

        # Check if betting on the underdog
        if odds <= self.CONTRARIAN_THRESHOLD:
            confidence = Decimal("0.6") + (
                (self.CONTRARIAN_THRESHOLD - odds) * 2
            )

            return Signal(
                type=SignalType.CONTRARIAN,
                confidence=min(confidence, Decimal("0.95")),
                description=(
                    f"Betting on {trade.side.value} at {odds:.1%} odds "
                    f"(consensus is {opposite_odds:.1%})"
                ),
                metadata={
                    "side": trade.side.value,
                    "odds": float(odds),
                    "opposite_odds": float(opposite_odds),
                    "market_question": trade.market.question,
                },
            )

        return None


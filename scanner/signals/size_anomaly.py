"""Size anomaly signal detector."""

from decimal import Decimal

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Signal, SignalType, Trade, WalletProfile
from scanner.signals.base import SignalDetector


class SizeAnomalyDetector(SignalDetector):
    """
    Detect trades that are unusually large relative to:
    - Wallet's historical average
    - Market's typical trade size
    """

    def __init__(self, config: ScannerConfig | None = None):
        """
        Initialize detector.

        Args:
            config: Scanner configuration.
        """
        self._config = config or default_config
        self._multiplier = self._config.size_anomaly_multiplier

    @property
    def name(self) -> str:
        """Detector name."""
        return "SizeAnomalyDetector"

    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        """
        Check if trade size is anomalous.

        Args:
            trade: Trade to analyze.
            wallet_profile: Wallet profile for comparison.

        Returns:
            SizeAnomaly signal if trade is unusually large.
        """
        signals_data: dict = {
            "trade_size": float(trade.size_usd),
            "wallet": trade.wallet_address,
        }

        # Check against wallet history
        if wallet_profile and wallet_profile.avg_trade_size > 0:
            ratio = trade.size_usd / wallet_profile.avg_trade_size

            if ratio >= self._multiplier:
                signals_data["avg_trade_size"] = float(wallet_profile.avg_trade_size)
                signals_data["size_ratio"] = float(ratio)

                return Signal(
                    type=SignalType.SIZE_ANOMALY,
                    confidence=min(Decimal("0.95"), Decimal("0.5") + ratio / 10),
                    description=(
                        f"Trade is {ratio:.1f}x larger than wallet average "
                        f"(${wallet_profile.avg_trade_size:.2f})"
                    ),
                    metadata=signals_data,
                )

        # Check against market liquidity if available
        if trade.market and trade.market.liquidity > 0:
            liquidity_ratio = trade.size_usd / trade.market.liquidity

            # If trade is >5% of market liquidity, that's significant
            if liquidity_ratio >= Decimal("0.05"):
                signals_data["market_liquidity"] = float(trade.market.liquidity)
                signals_data["liquidity_ratio"] = float(liquidity_ratio)

                return Signal(
                    type=SignalType.SIZE_ANOMALY,
                    confidence=Decimal("0.8"),
                    description=(
                        f"Trade is {liquidity_ratio:.1%} of market liquidity"
                    ),
                    metadata=signals_data,
                )

        # Very large trades (>$50k) are always notable
        if trade.size_usd >= Decimal("50000"):
            return Signal(
                type=SignalType.SIZE_ANOMALY,
                confidence=Decimal("0.75"),
                description=f"Large trade: ${trade.size_usd:,.2f}",
                metadata=signals_data,
            )

        return None


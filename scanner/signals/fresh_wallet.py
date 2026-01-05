"""Fresh wallet signal detector."""

from decimal import Decimal

from scanner.config import ScannerConfig, config as default_config
from scanner.domain.models import Signal, SignalType, Trade, WalletProfile
from scanner.signals.base import SignalDetector


class FreshWalletDetector(SignalDetector):
    """
    Detect trades from fresh (new or low-activity) wallets.

    Fresh wallets making large trades can indicate insider knowledge
    or smart money entering a position.
    """

    def __init__(self, config: ScannerConfig | None = None):
        """
        Initialize detector.

        Args:
            config: Scanner configuration.
        """
        self._config = config or default_config
        self._trade_threshold = self._config.fresh_wallet_trade_threshold

    @property
    def name(self) -> str:
        """Detector name."""
        return "FreshWalletDetector"

    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        """
        Check if trade is from a fresh wallet.

        Args:
            trade: Trade to analyze.
            wallet_profile: Wallet profile with history.

        Returns:
            FreshWallet signal if conditions met.
        """
        if wallet_profile is None:
            # No profile data - assume fresh
            return Signal(
                type=SignalType.FRESH_WALLET,
                confidence=Decimal("0.7"),
                description="No wallet history available - likely new wallet",
                metadata={"wallet": trade.wallet_address},
            )

        if wallet_profile.is_fresh:
            # Calculate confidence based on how new the wallet is
            trade_count = wallet_profile.total_trades
            confidence = Decimal("0.9") - (Decimal(str(trade_count)) * Decimal("0.1"))
            confidence = max(confidence, Decimal("0.5"))

            return Signal(
                type=SignalType.FRESH_WALLET,
                confidence=confidence,
                description=f"Wallet has only {trade_count} previous trades",
                metadata={
                    "wallet": trade.wallet_address,
                    "total_trades": trade_count,
                    "days_active": wallet_profile.days_active,
                },
            )

        return None


"""Alert enrichment service."""

from datetime import datetime
from decimal import Decimal

from scanner.domain.models import Alert, Market, Signal, Trade, WalletProfile
from scanner.services.market_service import MarketService
from scanner.services.wallet_service import WalletService
from scanner.signals.base import SignalDetector


class AlertEnricher:
    """
    Enriches trades with additional context to create alerts.

    Responsibilities:
    - Fetch wallet profile
    - Fetch/update market data
    - Run signal detectors
    - Calculate confidence score
    """

    def __init__(
        self,
        wallet_service: WalletService,
        market_service: MarketService,
        signal_detectors: list[SignalDetector],
    ):
        """
        Initialize enricher.

        Args:
            wallet_service: Service for wallet data.
            market_service: Service for market data.
            signal_detectors: List of signal detectors to run.
        """
        self._wallet_service = wallet_service
        self._market_service = market_service
        self._detectors = signal_detectors

    async def enrich(self, trade: Trade) -> Alert | None:
        """
        Enrich a trade into a full alert.

        Args:
            trade: Trade to enrich.

        Returns:
            Alert with all enriched data, or None if enrichment fails.
        """
        # Fetch market data if not attached
        market = trade.market
        if market is None:
            market = await self._market_service.get_market(
                trade.market_id, 
                raw_data=trade.raw_data,
            )
            if market is None:
                return None

        # Fetch wallet profile
        wallet_profile = await self._wallet_service.get_profile(trade.wallet_address)

        # Run signal detectors
        signals = await self._detect_signals(trade, wallet_profile)

        # Calculate confidence score
        confidence = self._calculate_confidence(signals, trade, wallet_profile)

        # Get odds before/after (mock for now)
        # TODO: Track actual odds movement
        odds_before = market.current_odds_yes
        odds_after = market.current_odds_yes + Decimal("0.01")  # Mock change

        # Update wallet profile with this trade
        await self._wallet_service.update_profile(
            trade.wallet_address,
            trade.size_usd,
        )

        return Alert(
            trade=trade,
            market=market,
            wallet_profile=wallet_profile,
            signals=signals,
            odds_before=odds_before,
            odds_after=odds_after,
            confidence_score=confidence,
            timestamp=datetime.now(),
        )

    async def _detect_signals(
        self,
        trade: Trade,
        wallet_profile: WalletProfile,
    ) -> list[Signal]:
        """
        Run all signal detectors on a trade.

        Args:
            trade: Trade to analyze.
            wallet_profile: Wallet profile for context.

        Returns:
            List of detected signals.
        """
        signals = []

        for detector in self._detectors:
            if not detector.enabled:
                continue

            try:
                signal = await detector.detect(trade, wallet_profile)
                if signal:
                    signals.append(signal)
            except Exception as e:
                # Log but don't fail on detector errors
                # TODO: Add proper logging
                print(f"Detector {detector.name} failed: {e}")

        return signals

    def _calculate_confidence(
        self,
        signals: list[Signal],
        trade: Trade,
        wallet_profile: WalletProfile,
    ) -> Decimal:
        """
        Calculate overall confidence score for the alert.

        Combines individual signal confidences with trade characteristics.

        Args:
            signals: Detected signals.
            trade: The trade.
            wallet_profile: Wallet profile.

        Returns:
            Confidence score from 0 to 1.
        """
        if not signals:
            return Decimal("0.3")  # Base confidence

        # Average signal confidence
        avg_signal_conf = sum(s.confidence for s in signals) / len(signals)

        # Boost for multiple signals
        signal_count_boost = min(
            Decimal("0.1") * (len(signals) - 1),
            Decimal("0.2"),
        )

        # Boost for large trades
        size_boost = Decimal("0")
        if trade.size_usd >= Decimal("10000"):
            size_boost = Decimal("0.05")
        if trade.size_usd >= Decimal("50000"):
            size_boost = Decimal("0.1")

        # Boost for fresh wallets with high win rate (if known)
        winrate_boost = Decimal("0")
        if wallet_profile.win_rate >= Decimal("0.6") and wallet_profile.total_trades >= 10:
            winrate_boost = Decimal("0.1")

        confidence = avg_signal_conf + signal_count_boost + size_boost + winrate_boost

        return min(confidence, Decimal("0.99"))


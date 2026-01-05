"""Base signal detector interface."""

from abc import ABC, abstractmethod

from scanner.domain.models import Signal, Trade, WalletProfile


class SignalDetector(ABC):
    """Abstract base class for signal detectors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Detector name for logging."""
        ...

    @abstractmethod
    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        """
        Detect a signal on a trade.

        Args:
            trade: Trade to analyze.
            wallet_profile: Optional wallet profile for context.

        Returns:
            Signal if detected, None otherwise.
        """
        ...

    @property
    def enabled(self) -> bool:
        """Whether detector is enabled. Override to disable."""
        return True


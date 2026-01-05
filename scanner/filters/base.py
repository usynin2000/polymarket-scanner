"""Base filter interface and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from scanner.domain.models import Trade


@dataclass
class FilterResult:
    """Result of a filter check."""

    passed: bool
    reason: str | None = None

    @classmethod
    def accept(cls) -> "FilterResult":
        """Create a passing result."""
        return cls(passed=True)

    @classmethod
    def reject(cls, reason: str) -> "FilterResult":
        """Create a rejecting result with reason."""
        return cls(passed=False, reason=reason)


class TradeFilter(ABC):
    """Abstract base class for trade filters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Filter name for logging."""
        ...

    @abstractmethod
    async def check(self, trade: Trade) -> FilterResult:
        """
        Check if trade passes the filter.

        Args:
            trade: Trade to check.

        Returns:
            FilterResult indicating if trade passed and why not if rejected.
        """
        ...

    @property
    def enabled(self) -> bool:
        """Whether filter is enabled. Override to disable."""
        return True


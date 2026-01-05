"""Base output interface."""

from abc import ABC, abstractmethod

from scanner.domain.models import Alert


class AlertOutput(ABC):
    """Abstract base class for alert outputs."""

    @abstractmethod
    async def send(self, alert: Alert) -> None:
        """
        Send an alert to the output destination.

        Args:
            alert: Alert to output.
        """
        ...

    @property
    def enabled(self) -> bool:
        """Whether output is enabled."""
        return True


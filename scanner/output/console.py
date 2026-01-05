"""Console output for alerts."""

import logging
from datetime import datetime

from scanner.domain.models import Alert
from scanner.output.base import AlertOutput


class ConsoleOutput(AlertOutput):
    """
    Output alerts to console with structured formatting.

    Provides both human-readable and structured log formats.
    """

    # ANSI color codes for terminal
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
    }

    def __init__(self, use_colors: bool = True, use_logger: bool = False):
        """
        Initialize console output.

        Args:
            use_colors: Whether to use ANSI colors.
            use_logger: Whether to use logging module instead of print.
        """
        self._use_colors = use_colors
        self._use_logger = use_logger

        if use_logger:
            self._logger = logging.getLogger("scanner.alerts")

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors enabled."""
        if not self._use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    async def send(self, alert: Alert) -> None:
        """
        Output alert to console.

        Args:
            alert: Alert to display.
        """
        output = self._format_alert(alert)

        if self._use_logger:
            self._logger.info(output)
        else:
            print(output)

    def _format_alert(self, alert: Alert) -> str:
        """
        Format alert for console display.

        Args:
            alert: Alert to format.

        Returns:
            Formatted string.
        """
        lines = [
            "",
            self._color("=" * 60, "cyan"),
            self._color("[ALERT]", "bold") + f" {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            self._color("=" * 60, "cyan"),
            "",
            f"  {self._color('Market:', 'yellow')} {alert.market.question}",
            f"  {self._color('Category:', 'yellow')} {alert.market.category.value}",
            "",
            f"  {self._color('Wallet:', 'yellow')} {self._format_wallet(alert)}",
            f"  {self._color('Trade size:', 'yellow')} ${alert.trade.size_usd:,.2f}",
            f"  {self._color('Side:', 'yellow')} {self._format_side(alert)}",
            f"  {self._color('Price:', 'yellow')} {alert.trade.price:.2%}",
            "",
            f"  {self._color('Signals:', 'magenta')} {self._format_signals(alert)}",
            "",
            f"  {self._color('Odds before:', 'blue')} {alert.odds_before:.1%}",
            f"  {self._color('Odds after:', 'blue')} {alert.odds_after:.1%}",
            f"  {self._color('Odds change:', 'blue')} {self._format_odds_change(alert)}",
            "",
            f"  {self._color('Wallet profile:', 'cyan')}",
            f"    Total trades: {alert.wallet_profile.total_trades}",
            f"    Win rate: {alert.wallet_profile.win_rate:.1%}",
            f"    Avg trade size: ${alert.wallet_profile.avg_trade_size:,.2f}",
            "",
            f"  {self._color('Confidence score:', 'green')} "
            f"{self._format_confidence(alert.confidence_score)}",
            "",
            self._color("-" * 60, "cyan"),
        ]

        return "\n".join(lines)

    def _format_wallet(self, alert: Alert) -> str:
        """Format wallet address with fresh indicator."""
        wallet = alert.trade.wallet_address
        short = f"{wallet[:6]}...{wallet[-4:]}"

        if alert.wallet_profile.is_fresh:
            return f"{short} {self._color('[FRESH]', 'red')}"
        return short

    def _format_side(self, alert: Alert) -> str:
        """Format trade side with color."""
        if alert.trade.side.value == "YES":
            return self._color("YES ↑", "green")
        return self._color("NO ↓", "red")

    def _format_signals(self, alert: Alert) -> str:
        """Format signal list."""
        if not alert.signals:
            return self._color("None", "yellow")

        signal_strs = []
        for signal in alert.signals:
            signal_str = f"{signal.type.value} ({signal.confidence:.0%})"
            signal_strs.append(self._color(signal_str, "magenta"))

        return ", ".join(signal_strs)

    def _format_odds_change(self, alert: Alert) -> str:
        """Format odds change with direction."""
        change = alert.odds_after - alert.odds_before
        if change > 0:
            return self._color(f"+{change:.1%}", "green")
        elif change < 0:
            return self._color(f"{change:.1%}", "red")
        return "0%"

    def _format_confidence(self, confidence) -> str:
        """Format confidence with color based on level."""
        pct = f"{confidence:.0%}"

        if confidence >= 0.8:
            return self._color(f"🔥 {pct} HIGH", "red")
        elif confidence >= 0.6:
            return self._color(f"⚡ {pct} MEDIUM", "yellow")
        else:
            return self._color(f"💡 {pct} LOW", "blue")


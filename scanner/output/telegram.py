"""Telegram output for alerts."""

import logging
from decimal import Decimal

from aiogram import Bot
from aiogram.enums import ParseMode

from scanner.domain.models import Alert
from scanner.output.base import AlertOutput


logger = logging.getLogger(__name__)


class TelegramOutput(AlertOutput):
    """
    Output alerts to Telegram via bot.

    Sends formatted messages to a specified chat.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        enabled: bool = True,
    ):
        """
        Initialize Telegram output.

        Args:
            bot_token: Telegram bot token from @BotFather.
            chat_id: Chat ID to send messages to.
            enabled: Whether output is enabled.
        """
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._enabled = enabled
        self._bot: Bot | None = None

    @property
    def enabled(self) -> bool:
        """Whether output is enabled."""
        return self._enabled and bool(self._bot_token) and bool(self._chat_id)

    async def _get_bot(self) -> Bot:
        """Get or create bot instance (lazy initialization)."""
        if self._bot is None:
            self._bot = Bot(token=self._bot_token)
        return self._bot

    async def send(self, alert: Alert) -> None:
        """
        Send alert to Telegram.

        Args:
            alert: Alert to send.
        """
        if not self.enabled:
            return

        try:
            bot = await self._get_bot()
            message = self._format_alert(alert)
            await bot.send_message(
                chat_id=self._chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            logger.debug(f"Alert sent to Telegram: {alert.trade.id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    def _format_alert(self, alert: Alert) -> str:
        """
        Format alert for Telegram.

        Args:
            alert: Alert to format.

        Returns:
            HTML-formatted message string.
        """
        # Confidence emoji
        confidence_emoji = self._get_confidence_emoji(alert.confidence_score)

        # Side formatting
        side_emoji = "🟢" if alert.trade.side.value == "YES" else "🔴"
        side_text = f"{side_emoji} {alert.trade.side.value}"

        # Fresh wallet indicator
        wallet_short = f"{alert.trade.wallet_address[:6]}...{alert.trade.wallet_address[-4:]}"
        wallet_text = f"🆕 {wallet_short}" if alert.wallet_profile.is_fresh else wallet_short

        # Signals formatting
        signals_text = self._format_signals(alert)

        # Odds change
        odds_change = alert.odds_after - alert.odds_before
        odds_change_text = f"+{odds_change:.1%}" if odds_change > 0 else f"{odds_change:.1%}"

        # Build message
        lines = [
            "=====================\n"
            f"{confidence_emoji} <b>POLYMARKET ALERT</b>",
            "",
            f"📊 <b>{self._escape_html(alert.market.question)}</b>",
            f"📁 {alert.market.category.value}",
            "",
            f"👛 <code>{wallet_text}</code>",
            f"💰 <b>${alert.trade.size_usd:,.0f}</b>",
            f"📈 {side_text} @ {alert.trade.price:.1%}",
            "",
            f"⚡ <b>Сигналы:</b> {signals_text}",
            "",
            f"📉 Odds: {alert.odds_before:.1%} → {alert.odds_after:.1%} ({odds_change_text})",
            "",
            f"🎯 Confidence: <b>{alert.confidence_score:.0%}</b>",
            "",
            f"👤 Wallet stats:",
            f"   • Trades: {alert.wallet_profile.total_trades}",
            f"   • Win rate: {alert.wallet_profile.win_rate:.0%}",
            f"   • Avg size: ${alert.wallet_profile.avg_trade_size:,.0f}",
        ]

        return "\n".join(lines)

    def _format_signals(self, alert: Alert) -> str:
        """Format signals list."""
        if not alert.signals:
            return "None"

        signal_emojis = {
            "FreshWallet": "🆕",
            "SizeAnomaly": "📊",
            "TimingSignal": "⏰",
            "OddsMovement": "📈",
            "Contrarian": "🔄",
            "TradeClustering": "🎯",
        }

        parts = []
        for signal in alert.signals:
            emoji = signal_emojis.get(signal.type.value, "⚡")
            parts.append(f"{emoji}{signal.type.value}")

        return ", ".join(parts)

    def _get_confidence_emoji(self, confidence: Decimal) -> str:
        """Get emoji based on confidence level."""
        if confidence >= Decimal("0.8"):
            return "🔥"
        elif confidence >= Decimal("0.6"):
            return "⚡"
        else:
            return "💡"

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    async def close(self) -> None:
        """Close bot session."""
        if self._bot:
            await self._bot.session.close()
            self._bot = None


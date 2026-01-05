"""Domain models for the Polymarket scanner."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to UTC-aware, or return as-is if already aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class MarketCategory(str, Enum):
    """Market category classification."""

    POLITICS = "politics"
    SPORTS = "sports"
    CRYPTO = "crypto"
    ENTERTAINMENT = "entertainment"
    SCIENCE = "science"
    ECONOMICS = "economics"
    TIME_BASED = "time_based"
    OTHER = "other"


class TradeSide(str, Enum):
    """Trade side - YES or NO position."""

    YES = "YES"
    NO = "NO"


class SignalType(str, Enum):
    """Types of signals that can be detected."""

    FRESH_WALLET = "FreshWallet"
    SIZE_ANOMALY = "SizeAnomaly"
    TIMING_SIGNAL = "TimingSignal"
    ODDS_MOVEMENT = "OddsMovement"
    CONTRARIAN = "Contrarian"
    TRADE_CLUSTERING = "TradeClustering"


@dataclass
class Market:
    """Market information."""

    id: str
    question: str
    category: MarketCategory
    end_date: datetime | None = None
    current_odds_yes: Decimal = Decimal("0.5")
    current_odds_no: Decimal = Decimal("0.5")
    volume_24h: Decimal = Decimal("0")
    liquidity: Decimal = Decimal("0")
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if market is still active."""
        if self.end_date is None:
            return True
        # Handle both timezone-aware and naive datetimes
        end = _make_aware(self.end_date)
        return _utc_now() < end


@dataclass
class Trade:
    """A single trade from Polymarket."""

    id: str
    market_id: str
    wallet_address: str
    side: TradeSide
    size_usd: Decimal
    price: Decimal
    timestamp: datetime
    market: Market | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy trade."""
        return self.side == TradeSide.YES


@dataclass
class WalletProfile:
    """Wallet profile with historical data."""

    address: str
    total_trades: int = 0
    total_volume_usd: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0.5")
    avg_trade_size: Decimal = Decimal("0")
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    preferred_categories: list[MarketCategory] = field(default_factory=list)
    is_suspected_lp: bool = False

    @property
    def is_fresh(self) -> bool:
        """Check if wallet is fresh (new or low activity)."""
        return self.total_trades < 5

    @property
    def days_active(self) -> int:
        """Calculate days since first activity."""
        if self.first_seen is None:
            return 0
        # Handle both timezone-aware and naive datetimes
        first = _make_aware(self.first_seen)
        return (_utc_now() - first).days


@dataclass
class Signal:
    """A detected signal on a trade."""

    type: SignalType
    confidence: Decimal
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """Enriched alert ready for output."""

    trade: Trade
    market: Market
    wallet_profile: WalletProfile
    signals: list[Signal]
    odds_before: Decimal
    odds_after: Decimal
    confidence_score: Decimal
    timestamp: datetime = field(default_factory=_utc_now)

    @property
    def signal_types(self) -> list[SignalType]:
        """Get list of signal types."""
        return [s.type for s in self.signals]


# Polymarket Trade Scanner

Real-time scanner for Polymarket trades with signal detection and alert generation.

## Features

- 🔌 **WebSocket Integration** - Real-time trade streaming from Polymarket CLOB
- 🔍 **Smart Filtering** - Market category, trade size, and LP detection filters
- 🎯 **Signal Detection** - Multiple signal detectors for trade analysis
- 📊 **Alert Enrichment** - Wallet profiles, market data, and confidence scoring
- 🖥️ **Console Output** - Formatted alerts with color-coded information
- 📱 **Telegram Notifications** - Real-time alerts via Telegram bot

## Architecture

```
Polymarket CLOB WebSocket
        ↓
   Trade received
        ↓
   Market Filter ──→ (excluded categories)
        ↓
   Size Filter ──→ (trades < $2,000)
        ↓
   LP Detection ──→ (liquidity providers)
        ↓
   Signal Detection
   • Fresh Wallet
   • Size Anomaly
   • Timing Signal
   • Odds Movement
   • Contrarian
   • Trade Clustering
        ↓
   Alert Enrichment
   • Wallet profile
   • Win rate estimation
   • Market odds
        ↓
   Output
   • Console (formatted)
   • Telegram (optional)
```

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd polymarket-scanner

# Create virtual environment with uv
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"
```

## Usage

### Run with Mock Data (Development)

```bash
# Using the installed script
polymarket-scanner

# Or directly
python -m scanner.main
```

### Run with Live Data (requires Private Key)

```bash
# Set your private key (required for CLOB API access)
export SCANNER_PRIVATE_KEY="your_private_key_without_0x_prefix"

# Run in live mode
polymarket-scanner --live
```

Or create a `.env` file:

```env
# Your Ethereum private key (without 0x prefix)
# ⚠️ NEVER commit your real private key to git!
SCANNER_PRIVATE_KEY=abc123...

# Telegram notifications (optional)
SCANNER_TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
SCANNER_TELEGRAM_CHAT_ID=123456789

# Optional settings
SCANNER_MIN_TRADE_SIZE_USD=2000
SCANNER_LOG_LEVEL=INFO
```

Then run:

```bash
polymarket-scanner --live
```

### Configuration

Configuration via environment variables (prefix `SCANNER_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SCANNER_PRIVATE_KEY` | None | **Required for live mode.** Your ETH private key |
| `SCANNER_MIN_TRADE_SIZE_USD` | 2000 | Minimum trade size to process |
| `SCANNER_CHAIN_ID` | 137 | Polygon mainnet chain ID |
| `SCANNER_LOG_LEVEL` | INFO | Logging verbosity |
| `SCANNER_TELEGRAM_BOT_TOKEN` | None | Telegram bot token from @BotFather |
| `SCANNER_TELEGRAM_CHAT_ID` | None | Telegram chat ID for notifications |
| `SCANNER_TELEGRAM_ENABLED` | true | Enable/disable Telegram output |

### How to get your Private Key

1. **MetaMask**: Settings → Security & Privacy → Reveal Secret Recovery Phrase → Export Private Key
2. **Rabby**: Settings → Security → Export Private Key  
3. **Hardware Wallet**: Export from the wallet software

⚠️ **Security Warning**: 
- Never share your private key
- Never commit it to git (add `.env` to `.gitignore`)
- Consider using a dedicated wallet with limited funds for scanning

### Telegram Setup

1. **Create a bot** via [@BotFather](https://t.me/BotFather):
   - Send `/newbot` and follow instructions
   - Copy the token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get your Chat ID**:
   - Message [@userinfobot](https://t.me/userinfobot) to get your user ID
   - Or for a channel: add bot as admin and use channel ID (e.g., `-100123456789`)

3. **Configure**:
   ```bash
   export SCANNER_TELEGRAM_BOT_TOKEN="your_bot_token"
   export SCANNER_TELEGRAM_CHAT_ID="your_chat_id"
   ```

4. **Start the bot**: Send `/start` to your bot in Telegram before running the scanner

## Project Structure

```
polymarket-scanner/
├── scanner/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── main.py             # Entry point
│   ├── pipeline.py         # Processing pipeline
│   ├── domain/
│   │   ├── __init__.py
│   │   └── models.py       # Data models (Trade, Alert, etc.)
│   ├── filters/
│   │   ├── __init__.py
│   │   ├── base.py         # Filter interface
│   │   ├── market_filter.py
│   │   ├── size_filter.py
│   │   └── lp_filter.py
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── base.py         # Detector interface
│   │   ├── fresh_wallet.py
│   │   ├── size_anomaly.py
│   │   ├── timing.py
│   │   ├── odds_movement.py
│   │   ├── contrarian.py
│   │   └── clustering.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── enrichment.py   # Alert enrichment
│   │   ├── wallet_service.py
│   │   └── market_service.py
│   ├── transport/
│   │   ├── __init__.py
│   │   ├── websocket.py    # Polymarket WebSocket
│   │   └── mock.py         # Mock data generator
│   └── output/
│       ├── __init__.py
│       ├── base.py         # Output interface
│       ├── console.py      # Console formatter
│       └── telegram.py     # Telegram bot output
├── pyproject.toml
└── README.md
```

## Extension Points

### Adding a New Signal Detector

```python
from scanner.signals.base import SignalDetector
from scanner.domain.models import Signal, SignalType, Trade, WalletProfile

class MyCustomDetector(SignalDetector):
    @property
    def name(self) -> str:
        return "MyCustomDetector"

    async def detect(
        self,
        trade: Trade,
        wallet_profile: WalletProfile | None = None,
    ) -> Signal | None:
        # Your detection logic here
        if some_condition:
            return Signal(
                type=SignalType.SIZE_ANOMALY,  # or add new type
                confidence=Decimal("0.8"),
                description="Custom signal detected",
            )
        return None
```

### Adding a New Output

Telegram is already implemented! For custom outputs:

```python
from scanner.output.base import AlertOutput
from scanner.domain.models import Alert

class CustomOutput(AlertOutput):
    async def send(self, alert: Alert) -> None:
        # Your custom output logic
        message = self._format_message(alert)
        await self._send_somewhere(message)
```

### Adding Database Persistence

```python
from scanner.output.base import AlertOutput

class DatabaseOutput(AlertOutput):
    async def send(self, alert: Alert) -> None:
        await self._db.insert("alerts", {
            "trade_id": alert.trade.id,
            "market_id": alert.market.id,
            "signals": [s.type.value for s in alert.signals],
            "confidence": float(alert.confidence_score),
        })
```

## Sample Output

```
============================================================
[ALERT] 2026-01-05 15:30:45
============================================================

  Market: Will AI surpass human-level reasoning by 2030?
  Category: science

  Wallet: 0x742d...fE10 [FRESH]
  Trade size: $15,250.00
  Side: YES ↑
  Price: 65.00%

  Signals: FreshWallet (85%), SizeAnomaly (75%)

  Odds before: 63.0%
  Odds after: 65.0%
  Odds change: +2.0%

  Wallet profile:
    Total trades: 3
    Win rate: 50.0%
    Avg trade size: $2,500.00

  Confidence score: 🔥 82% HIGH

------------------------------------------------------------
```

## TODO

- [ ] Implement real Polymarket WebSocket parsing
- [ ] Add historical data fetching for wallets
- [ ] Implement ML-based confidence scoring
- [x] Add Telegram output module
- [ ] Add Discord output module
- [ ] Add database persistence
- [ ] Add metrics and monitoring

## License

MIT

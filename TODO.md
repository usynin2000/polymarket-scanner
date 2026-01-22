git # TO-DO для Production-Ready Polymarket Scanner

> **Статус:** Текущая версия - MVP с моковыми данными
> **Цель:** Полноценный production-ready сканер с реальными API, persistence, мониторингом и fault tolerance

---

## 🔴 КРИТИЧНЫЕ КОМПОНЕНТЫ (P0)

### 1. WalletService - Реальные API интеграции

**Файл:** `scanner/services/wallet_service.py`

**Проблема:** Полностью моковая реализация, не использует реальные данные

**Необходимые API и методы:**

#### 1.1 Polymarket Subgraph API (GraphQL)
```python
async def _fetch_wallet_from_subgraph(self, wallet_address: str) -> dict:
    """
    Fetch wallet data from Polymarket subgraph.

    Endpoint: https://api.thegraph.com/subgraphs/name/polymarket/polymarket

    GraphQL Query:
    {
      user(id: "0x...") {
        id
        tradesCount
        totalVolume
        positions {
          market { question }
          outcomeIndex
          size
          value
        }
        trades {
          timestamp
          outcomeIndex
          size
          price
          market { question }
        }
      }
    }

    Поля для извлечения:
    - total_trades: user.tradesCount
    - total_volume_usd: user.totalVolume
    - first_seen: min(trades[].timestamp)
    - last_seen: max(trades[].timestamp)
    - win_rate: calculate from closed positions
    """
    pass
```

#### 1.2 Polygon Blockchain API (для on-chain данных)
```python
async def _fetch_wallet_on_chain_data(self, wallet_address: str) -> dict:
    """
    Fetch wallet on-chain activity from Polygon.

    API Options:
    1. Polygonscan API: https://api.polygonscan.com/api
       - Endpoint: ?module=account&action=tokentx&address=0x...
       - Нужен API ключ: https://polygonscan.com/apis

    2. Alchemy API: https://polygon-mainnet.g.alchemy.com/v2/{API_KEY}
       - Method: alchemy_getAssetTransfers
       - Более надежный, но платный

    3. Quicknode: https://docs.quicknode.com/
       - eth_getBalance, eth_getTransactionCount

    Данные:
    - Возраст кошелька (первая транзакция)
    - Количество транзакций
    - Баланс USDC/MATIC
    - Взаимодействие с контрактами Polymarket
    """
    pass
```

#### 1.3 Internal Database для кэширования
```python
async def _fetch_wallet_from_db(self, wallet_address: str) -> WalletProfile | None:
    """
    Fetch cached wallet profile from database.

    Tables needed:
    - wallet_profiles (address, total_trades, total_volume, win_rate, ...)
    - wallet_trades (wallet_address, trade_id, timestamp, size, outcome, ...)
    - wallet_stats_hourly (для time-series анализа)

    Cache TTL: 5 minutes for active wallets, 1 hour for inactive
    """
    pass

async def _save_wallet_to_db(self, profile: WalletProfile) -> None:
    """Save or update wallet profile in database."""
    pass
```

#### 1.4 Win Rate Calculation
```python
async def calculate_win_rate(self, wallet_address: str) -> Decimal:
    """
    Calculate real win rate from closed positions.

    Logic:
    1. Fetch all resolved markets where wallet had positions
    2. Check if position was winning side
    3. Weight by position size (optional)
    4. Calculate: winning_positions / total_positions

    Sources:
    - Polymarket API: /markets?closed=true
    - Subgraph: positions + market.resolved
    """
    pass
```

#### 1.5 Category Preferences
```python
async def calculate_category_preferences(
    self,
    wallet_address: str
) -> list[MarketCategory]:
    """
    Analyze wallet's preferred market categories.

    Logic:
    1. Group trades by market category
    2. Calculate volume per category
    3. Return top 3 categories by volume

    Use case: Detect specialized traders (sports bettors, politics traders, etc.)
    """
    pass
```

#### 1.6 LP Detection Enhancement
```python
async def detect_lp_behavior(self, wallet_address: str) -> dict:
    """
    Advanced LP detection using multiple heuristics.

    Indicators:
    - Balanced YES/NO positions over time
    - High trade frequency (>10 trades/hour)
    - Small price impact trades
    - Presence in order book (limit orders)
    - Low variance in trade sizes

    Return:
    {
        "is_lp": bool,
        "confidence": Decimal,
        "indicators": ["balanced_positions", "high_frequency", ...]
    }
    """
    pass
```

---

### 2. MarketService - Дополнительные методы

**Файл:** `scanner/services/market_service.py`

#### 2.1 Order Book Data
```python
async def get_order_book(self, market_id: str) -> dict:
    """
    Fetch order book for a market.

    CLOB API: GET /book?token_id={token_id}

    Returns:
    {
        "bids": [{"price": "0.55", "size": "1000"}, ...],
        "asks": [{"price": "0.56", "size": "500"}, ...],
        "spread": Decimal("0.01"),
        "depth": Decimal("50000")  # Total liquidity within 1% of mid
    }

    Use case: Detect low liquidity markets, calculate market impact
    """
    pass
```

#### 2.2 Historical Price Data
```python
async def get_price_history(
    self,
    market_id: str,
    interval: str = "1h",
    lookback_hours: int = 24
) -> list[dict]:
    """
    Fetch historical OHLCV data for a market.

    Sources:
    1. Polymarket API: /prices (if exists)
    2. Subgraph: aggregate trades into candles
    3. Internal database: pre-computed candles

    Returns: [
        {
            "timestamp": datetime,
            "open": Decimal,
            "high": Decimal,
            "low": Decimal,
            "close": Decimal,
            "volume": Decimal
        },
        ...
    ]

    Use case: Calculate volatility, detect momentum, odds movement analysis
    """
    pass
```

#### 2.3 Market Metadata Enhancement
```python
async def get_market_metadata(self, market_id: str) -> dict:
    """
    Fetch extended market metadata.

    Additional fields needed:
    - created_at: Market creation timestamp
    - volume_total: All-time volume
    - trades_count: Total number of trades
    - unique_traders: Number of unique wallets
    - outcome_tokens: YES/NO token addresses
    - resolution_source: Oracle/resolution criteria
    - tags: List of tags for better categorization

    Gamma API: /markets/{slug} has most of this
    """
    pass
```

#### 2.4 Related Markets
```python
async def get_related_markets(self, market_id: str, limit: int = 5) -> list[Market]:
    """
    Find related/similar markets.

    Logic:
    - Same event/topic
    - Similar tags
    - Same resolution date
    - Correlated price movements

    Use case: Detect arbitrage opportunities, validate signals across related markets
    """
    pass
```

---

### 3. Transport Layer - Улучшения WebSocket и REST

**Файлы:** `scanner/transport/websocket.py`, `scanner/transport/clob_client.py`

#### 3.1 WebSocket Reconnection с Exponential Backoff
```python
class ReconnectionManager:
    """
    Управление переподключениями с exponential backoff.

    Features:
    - Exponential backoff: 1s, 2s, 4s, 8s, ..., max 60s
    - Jitter для предотвращения thundering herd
    - Circuit breaker: stop after N failed attempts
    - Health check перед reconnect
    """

    async def reconnect_with_backoff(self, max_attempts: int = 10) -> bool:
        pass
```

#### 3.2 Rate Limiting для API запросов
```python
class RateLimiter:
    """
    Rate limiting для защиты от API бана.

    Limits для Polymarket:
    - CLOB API: 100 requests/min (estimate)
    - Gamma API: 60 requests/min (estimate)
    - Data API: Unknown (need testing)

    Implementations:
    - Token bucket algorithm
    - Per-endpoint limits
    - Automatic retry with backoff when rate limited (429 response)
    """

    async def acquire(self, endpoint: str) -> None:
        """Wait until rate limit allows request."""
        pass
```

#### 3.3 Request Retry Логика
```python
class RetryConfig:
    """
    Retry configuration for API requests.

    Retry on:
    - Network errors (ConnectionError, TimeoutError)
    - Server errors (500, 502, 503, 504)
    - Rate limits (429) - with longer backoff

    Don't retry on:
    - Client errors (400, 401, 403, 404)
    - Successful responses (200-299)

    Strategy:
    - Max retries: 3
    - Backoff: exponential (1s, 2s, 4s)
    - Timeout: 30s per request
    """

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        pass
```

#### 3.4 Circuit Breaker Pattern
```python
class CircuitBreaker:
    """
    Circuit breaker для защиты от каскадных сбоев.

    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing if service recovered

    Configuration:
    - Failure threshold: 5 consecutive failures
    - Recovery timeout: 60 seconds
    - Success threshold in half-open: 2 successes

    Use case: Если Polymarket API недоступен, переключиться на
             резервный источник или graceful degradation
    """

    async def call(self, func: Callable) -> Any:
        pass
```

---

### 4. Database Layer - Persistence

**Новый модуль:** `scanner/database/`

#### 4.1 Database Schema
```python
"""
PostgreSQL schema (предпочтительно) или SQLite для dev.

Tables:

1. trades
   - id (UUID, PK)
   - market_id (VARCHAR)
   - wallet_address (VARCHAR, indexed)
   - side (ENUM: YES/NO)
   - size_usd (NUMERIC)
   - price (NUMERIC)
   - timestamp (TIMESTAMP, indexed)
   - raw_data (JSONB)
   - created_at (TIMESTAMP)

2. alerts
   - id (UUID, PK)
   - trade_id (UUID, FK)
   - market_id (VARCHAR)
   - wallet_address (VARCHAR)
   - signals (JSONB)  # Array of signal types
   - confidence_score (NUMERIC)
   - timestamp (TIMESTAMP)
   - sent_telegram (BOOLEAN)
   - sent_discord (BOOLEAN)

3. wallet_profiles
   - address (VARCHAR, PK)
   - total_trades (INTEGER)
   - total_volume_usd (NUMERIC)
   - win_rate (NUMERIC)
   - avg_trade_size (NUMERIC)
   - first_seen (TIMESTAMP)
   - last_seen (TIMESTAMP)
   - is_suspected_lp (BOOLEAN)
   - updated_at (TIMESTAMP)

4. markets
   - id (VARCHAR, PK)
   - question (TEXT)
   - category (VARCHAR)
   - end_date (TIMESTAMP)
   - volume_24h (NUMERIC)
   - liquidity (NUMERIC)
   - metadata (JSONB)
   - updated_at (TIMESTAMP)

5. wallet_trades (для статистики)
   - wallet_address (VARCHAR)
   - trade_id (UUID)
   - market_id (VARCHAR)
   - timestamp (TIMESTAMP)
   - size_usd (NUMERIC)
   - outcome (VARCHAR)
   - is_resolved (BOOLEAN)
   - is_winning (BOOLEAN, nullable)

   Indexes:
   - (wallet_address, timestamp) для time-series queries
   - (market_id, timestamp)

6. system_metrics (для мониторинга)
   - timestamp (TIMESTAMP)
   - metric_name (VARCHAR)
   - metric_value (NUMERIC)
   - labels (JSONB)
"""
```

#### 4.2 Database Repository Pattern
```python
class TradeRepository:
    """CRUD operations for trades."""

    async def save_trade(self, trade: Trade) -> None:
        """Save trade to database."""
        pass

    async def get_trade(self, trade_id: str) -> Trade | None:
        """Fetch trade by ID."""
        pass

    async def get_wallet_trades(
        self,
        wallet_address: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[Trade]:
        """Get trades for a wallet."""
        pass

    async def get_market_trades(
        self,
        market_id: str,
        since: datetime | None = None
    ) -> list[Trade]:
        """Get recent trades for a market."""
        pass

class AlertRepository:
    """CRUD operations for alerts."""

    async def save_alert(self, alert: Alert) -> None:
        pass

    async def get_alerts_by_wallet(
        self,
        wallet_address: str,
        hours: int = 24
    ) -> list[Alert]:
        pass

class WalletRepository:
    """CRUD operations for wallet profiles."""

    async def get_profile(self, address: str) -> WalletProfile | None:
        pass

    async def save_profile(self, profile: WalletProfile) -> None:
        pass

    async def update_stats(
        self,
        address: str,
        trade_size: Decimal
    ) -> None:
        """Incrementally update wallet stats."""
        pass
```

#### 4.3 Database Migrations
```python
"""
Use Alembic for migrations.

Setup:
1. alembic init migrations
2. Configure alembic.ini with DB URL
3. Create initial migration: alembic revision --autogenerate -m "Initial schema"
4. Apply: alembic upgrade head

Need scripts:
- migrations/versions/001_initial_schema.py
- migrations/versions/002_add_indexes.py
- migrations/versions/003_add_wallet_categories.py
"""
```

#### 4.4 Connection Pooling
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

class Database:
    """
    Database connection manager with pooling.

    Configuration:
    - Pool size: 20 connections
    - Max overflow: 10
    - Pool timeout: 30s
    - Pool recycle: 3600s (1 hour)

    Support for:
    - PostgreSQL: asyncpg driver
    - SQLite: aiosqlite for development
    """

    def __init__(self, database_url: str):
        self.engine = create_async_engine(
            database_url,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
        )

    async def get_session(self) -> AsyncSession:
        pass
```

---

### 5. Caching Layer

**Новый модуль:** `scanner/cache/`

#### 5.1 Redis Cache для Hot Data
```python
class RedisCache:
    """
    Redis cache for frequently accessed data.

    Use cases:
    - Wallet profiles (TTL: 5 min)
    - Market data (TTL: 1 min)
    - Order books (TTL: 10 sec)
    - API responses (TTL: varies)

    Features:
    - Automatic serialization (pickle or json)
    - TTL support
    - Key namespacing
    - Bulk get/set
    - LRU eviction

    Fallback: In-memory LRU cache if Redis unavailable
    """

    async def get(self, key: str) -> Any | None:
        pass

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        pass
```

#### 5.2 Multi-Level Cache Strategy
```python
class CacheManager:
    """
    Multi-level caching: Memory → Redis → Database → API

    L1: In-memory cache (LRU, 1000 items)
    L2: Redis cache (distributed, TTL-based)
    L3: Database (persistent)
    L4: External API (slowest, rate-limited)

    Read strategy:
    1. Check L1, return if hit
    2. Check L2, populate L1 if hit
    3. Check L3, populate L2+L1 if hit
    4. Fetch from L4, populate all levels

    Write strategy:
    - Write-through: update all levels
    - Write-behind: async update L3+L4
    """

    async def get_with_cache(
        self,
        key: str,
        fetch_func: Callable,
        ttl: int = 300
    ) -> Any:
        pass
```

---

### 6. Signal Detectors - Реальная имплементация

**Файлы:** `scanner/signals/*.py`

#### 6.1 OddsMovementDetector - Реальное отслеживание
```python
# scanner/signals/odds_movement.py

class OddsMovementDetector(SignalDetector):
    """
    Detect significant odds movements around a trade.

    Current: Mock implementation
    Need:
    1. Track odds before trade (from order book or last price)
    2. Track odds after trade (immediate market impact)
    3. Calculate slippage
    4. Detect if trade moved market significantly

    Data sources:
    - Pre-trade: Order book snapshot or last trade price
    - Post-trade: Next trade price or book midpoint
    - Historical: Price history from DB or API

    Thresholds:
    - Significant move: >2% price change
    - High impact: Trade is >5% of market liquidity
    """

    async def detect(self, trade: Trade, wallet_profile: WalletProfile | None) -> Signal | None:
        # Need to implement:
        # 1. Get odds before trade (cache or DB)
        # 2. Get odds after trade (wait for next update or check book)
        # 3. Calculate movement and confidence
        pass

    async def _get_odds_snapshot(self, market_id: str, timestamp: datetime) -> Decimal:
        """Get market odds at specific timestamp."""
        pass
```

#### 6.2 ClusteringDetector - Улучшенная логика
```python
# scanner/signals/clustering.py

class ClusteringDetector(SignalDetector):
    """
    Detect when multiple wallets trade same market in short time.

    Current: Basic time window check
    Need:
    1. Track all trades per market in time window
    2. Detect coordinated trading (multiple wallets, same side)
    3. Calculate correlation between wallets
    4. Detect wash trading patterns

    Advanced features:
    - Wallet clustering by on-chain analysis (shared funding source)
    - Temporal clustering (trades within seconds of each other)
    - Volume clustering (similar trade sizes)

    Data needed:
    - Recent trades per market (from DB or cache)
    - Wallet relationships (from on-chain analysis)
    """

    async def detect(self, trade: Trade, wallet_profile: WalletProfile | None) -> Signal | None:
        # Implement:
        # 1. Query recent trades for same market
        # 2. Check for clustering patterns
        # 3. Calculate confidence based on cluster size and timing
        pass

    async def _get_recent_market_trades(
        self,
        market_id: str,
        window_seconds: int = 300
    ) -> list[Trade]:
        """Fetch recent trades for market from DB."""
        pass
```

#### 6.3 TimingDetector - События и катализаторы
```python
# scanner/signals/timing.py

class TimingDetector(SignalDetector):
    """
    Detect trades made around significant events.

    Current: Stub implementation
    Need:
    1. External events API integration
    2. News API for real-time events
    3. Social media monitoring (Twitter, Reddit)
    4. Calendar of scheduled events (elections, earnings, etc.)

    Event sources:
    - NewsAPI.org
    - Twitter API v2
    - Reddit API
    - Google Calendar API
    - Custom events database

    Logic:
    - Check if trade made within 1 hour of relevant event
    - Match event keywords to market question
    - Higher confidence for trades immediately after breaking news
    """

    async def detect(self, trade: Trade, wallet_profile: WalletProfile | None) -> Signal | None:
        # Implement:
        # 1. Fetch recent events related to market category
        # 2. Match events to market question (NLP)
        # 3. Check timing correlation
        pass

    async def _fetch_recent_events(
        self,
        category: MarketCategory,
        hours: int = 24
    ) -> list[dict]:
        """Fetch recent events from external APIs."""
        pass
```

#### 6.4 ContrarianDetector - Реальная логика
```python
# scanner/signals/contrarian.py

class ContrarianDetector(SignalDetector):
    """
    Detect contrarian trades (against market consensus).

    Current: Mock
    Need:
    1. Calculate market consensus (from odds)
    2. Detect if trade goes against consensus
    3. Check if wallet has history of successful contrarian trades

    Logic:
    - Consensus: odds >70% or <30% (strong market belief)
    - Contrarian: trade on opposite side
    - Confidence boost if wallet has good contrarian track record

    Data needed:
    - Current market odds
    - Wallet's historical contrarian trade outcomes
    """

    async def detect(self, trade: Trade, wallet_profile: WalletProfile | None) -> Signal | None:
        # Implement:
        # 1. Check if market has strong consensus
        # 2. Check if trade is contrarian
        # 3. Boost confidence if wallet has good contrarian history
        pass
```

---

## 🟡 ВАЖНЫЕ КОМПОНЕНТЫ (P1)

### 7. Monitoring & Observability

**Новый модуль:** `scanner/monitoring/`

#### 7.1 Prometheus Metrics
```python
from prometheus_client import Counter, Histogram, Gauge

# Metrics to track:
trades_received = Counter('scanner_trades_received_total', 'Total trades received')
trades_filtered = Counter('scanner_trades_filtered_total', 'Trades filtered out', ['filter_name'])
alerts_generated = Counter('scanner_alerts_generated_total', 'Total alerts generated')
api_requests = Counter('scanner_api_requests_total', 'API requests', ['endpoint', 'status'])
api_latency = Histogram('scanner_api_latency_seconds', 'API latency', ['endpoint'])
websocket_status = Gauge('scanner_websocket_connected', 'WebSocket connection status')
cache_hits = Counter('scanner_cache_hits_total', 'Cache hits', ['cache_level'])
cache_misses = Counter('scanner_cache_misses_total', 'Cache misses', ['cache_level'])

# Endpoint for Prometheus scraping:
# GET /metrics
```

#### 7.2 Health Checks
```python
class HealthCheck:
    """
    Health check endpoints for monitoring.

    Checks:
    - WebSocket connection status
    - Database connectivity
    - Redis connectivity
    - API endpoints availability
    - Last trade timestamp (detect stalls)
    - Memory usage
    - CPU usage

    Endpoints:
    - GET /health - Simple alive check
    - GET /health/ready - Readiness check (all dependencies)
    - GET /health/live - Liveness check (process alive)
    """

    async def check_health(self) -> dict:
        return {
            "status": "healthy",
            "checks": {
                "websocket": "connected",
                "database": "ok",
                "redis": "ok",
                "last_trade": "2026-01-22T10:30:00Z",
                "uptime_seconds": 3600,
            }
        }
```

#### 7.3 Structured Logging
```python
import structlog

"""
Replace standard logging with structlog for better observability.

Benefits:
- Structured JSON logs
- Automatic context propagation
- Integration with log aggregation (ELK, Grafana Loki)
- Better filtering and searching

Log format:
{
    "timestamp": "2026-01-22T10:30:00Z",
    "level": "info",
    "event": "trade_received",
    "trade_id": "0xabc...",
    "market_id": "0x123...",
    "wallet": "0x456...",
    "size_usd": 5000,
    "side": "YES"
}
"""

logger = structlog.get_logger()

# Usage:
logger.info(
    "trade_received",
    trade_id=trade.id,
    market_id=trade.market_id,
    size_usd=float(trade.size_usd)
)
```

#### 7.4 Error Tracking
```python
"""
Integrate Sentry for error tracking.

Setup:
1. pip install sentry-sdk
2. Configure in config.py:
   SENTRY_DSN = os.getenv("SENTRY_DSN")
3. Initialize in main.py:
   sentry_sdk.init(dsn=SENTRY_DSN, environment="production")

Features:
- Automatic exception capture
- Breadcrumbs (event trail before error)
- Performance monitoring
- Release tracking
"""
```

#### 7.5 Alerting для системных проблем
```python
class SystemAlerter:
    """
    Send alerts when system has issues.

    Alert conditions:
    - WebSocket disconnected >5 minutes
    - No trades received in 10 minutes
    - Database connection lost
    - Redis connection lost
    - API rate limit exceeded
    - Memory usage >90%
    - Error rate >10 errors/minute

    Alert channels:
    - Telegram (separate admin chat)
    - Email
    - PagerDuty (for critical issues)
    """

    async def send_system_alert(
        self,
        severity: str,  # "warning", "error", "critical"
        message: str,
        details: dict | None = None
    ) -> None:
        pass
```

---

### 8. Configuration Management

**Файл:** `scanner/config.py` (расширение)

#### 8.1 Environment-Specific Config
```python
class ScannerConfig(BaseSettings):
    """
    Добавить:

    # Environment
    environment: str = Field(default="development")  # development, staging, production

    # Database
    database_url: str = Field(default="sqlite:///scanner.db")
    database_pool_size: int = Field(default=20)

    # Redis
    redis_url: str | None = Field(default=None)
    redis_ttl_wallet: int = Field(default=300)  # 5 min
    redis_ttl_market: int = Field(default=60)   # 1 min

    # API Rate Limits
    api_rate_limit_clob: int = Field(default=100)  # requests per minute
    api_rate_limit_gamma: int = Field(default=60)

    # External APIs
    polygonscan_api_key: str | None = Field(default=None)
    alchemy_api_key: str | None = Field(default=None)
    newsapi_key: str | None = Field(default=None)
    twitter_bearer_token: str | None = Field(default=None)

    # Monitoring
    sentry_dsn: str | None = Field(default=None)
    prometheus_port: int = Field(default=9090)

    # Feature Flags
    feature_lp_filter: bool = Field(default=True)
    feature_odds_tracking: bool = Field(default=False)  # Not ready
    feature_news_events: bool = Field(default=False)    # Not ready

    # Performance
    max_concurrent_api_requests: int = Field(default=10)
    request_timeout_seconds: int = Field(default=30)

    # Alerting
    alert_admin_telegram_chat_id: str | None = Field(default=None)
    alert_email: str | None = Field(default=None)
    """
```

#### 8.2 Secrets Management
```python
"""
Use proper secrets management in production.

Options:
1. AWS Secrets Manager
2. HashiCorp Vault
3. Azure Key Vault
4. Google Secret Manager

Implementation:
- Fetch secrets at startup
- Cache with TTL
- Rotate automatically
- Never log secrets

Example:
async def load_secrets():
    secrets = await aws_secrets_manager.get_secret("polymarket-scanner")
    config.private_key = secrets["PRIVATE_KEY"]
    config.telegram_bot_token = secrets["TELEGRAM_BOT_TOKEN"]
"""
```

---

### 9. Testing

**Новая директория:** `tests/`

#### 9.1 Unit Tests
```python
"""
tests/
├── unit/
│   ├── test_filters.py
│   ├── test_signals.py
│   ├── test_services.py
│   ├── test_models.py
│   └── test_utils.py
├── integration/
│   ├── test_pipeline.py
│   ├── test_database.py
│   ├── test_api_clients.py
│   └── test_websocket.py
├── e2e/
│   └── test_full_flow.py
├── fixtures/
│   ├── trades.json
│   ├── markets.json
│   └── wallets.json
└── conftest.py

Coverage target: >80%

Key tests needed:
1. Filter logic with edge cases
2. Signal detection accuracy
3. API client error handling
4. Database operations
5. Cache behavior
6. WebSocket reconnection
7. Rate limiting
"""
```

#### 9.2 Mock API Responses
```python
"""
tests/mocks/polymarket_api.py

Mock responses for:
- Gamma API: /markets, /events
- CLOB API: /trades, /book
- Data API: /trades
- Subgraph: GraphQL queries

Use pytest fixtures and responses library.
"""
```

#### 9.3 Performance Tests
```python
"""
tests/performance/

Benchmarks:
- Trade processing throughput (trades/sec)
- Database write performance
- Cache hit rate
- API response times
- Memory usage over time
- CPU usage under load

Use pytest-benchmark or locust for load testing.
"""
```

---

### 10. CI/CD Pipeline

**Файлы:** `.github/workflows/` or `.gitlab-ci.yml`

#### 10.1 GitHub Actions Workflow
```yaml
# .github/workflows/main.yml

name: CI/CD

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install ruff mypy
      - run: ruff check .
      - run: mypy scanner/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -e ".[dev]"
      - run: pytest --cov=scanner --cov-report=xml
      - uses: codecov/codecov-action@v3

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: docker/build-push-action@v4
        with:
          push: true
          tags: polymarket-scanner:${{ github.sha }}

  deploy:
    needs: [lint, test, build]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: |
          # Deployment script
          # e.g., kubectl apply, docker-compose, etc.
```

---

### 11. Deployment & Infrastructure

**Файлы:** `deployment/`, `k8s/`, `terraform/`

#### 11.1 Docker Production Config
```dockerfile
# Dockerfile.prod

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 scanner
USER scanner

WORKDIR /app

# Install Python dependencies
COPY --chown=scanner:scanner requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=scanner:scanner scanner/ ./scanner/

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "scanner.main", "--live"]
```

#### 11.2 Docker Compose для Production
```yaml
# docker-compose.prod.yml

version: '3.8'

services:
  scanner:
    build:
      context: .
      dockerfile: Dockerfile.prod
    restart: unless-stopped
    environment:
      - SCANNER_DATABASE_URL=postgresql://scanner:password@postgres:5432/scanner
      - SCANNER_REDIS_URL=redis://redis:6379
      - SCANNER_PRIVATE_KEY=${PRIVATE_KEY}
      - SCANNER_TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - SCANNER_ENVIRONMENT=production
    depends_on:
      - postgres
      - redis
    networks:
      - scanner_network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  postgres:
    image: postgres:15
    restart: unless-stopped
    environment:
      - POSTGRES_DB=scanner
      - POSTGRES_USER=scanner
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - scanner_network

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - scanner_network

  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - scanner_network

  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - scanner_network

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  scanner_network:
```

#### 11.3 Kubernetes Manifests
```yaml
# k8s/deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: polymarket-scanner
spec:
  replicas: 1  # Single instance (WebSocket state)
  selector:
    matchLabels:
      app: polymarket-scanner
  template:
    metadata:
      labels:
        app: polymarket-scanner
    spec:
      containers:
      - name: scanner
        image: polymarket-scanner:latest
        env:
        - name: SCANNER_PRIVATE_KEY
          valueFrom:
            secretKeyRef:
              name: scanner-secrets
              key: private-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: scanner-service
spec:
  selector:
    app: polymarket-scanner
  ports:
  - name: metrics
    port: 9090
    targetPort: 9090
```

---

## 🟢 ЖЕЛАТЕЛЬНЫЕ УЛУЧШЕНИЯ (P2)

### 12. Machine Learning для Confidence Scoring

**Новый модуль:** `scanner/ml/`

#### 12.1 ML Model для Оценки Сигналов
```python
"""
Trained model to predict trade outcome based on signals.

Features:
- Wallet historical win rate
- Trade size relative to wallet average
- Market category
- Signal types detected
- Market liquidity
- Time of day
- Days until market resolution

Model types:
- Random Forest
- XGBoost
- Neural Network (simple)

Training data:
- Historical alerts + outcomes
- Need to track market resolutions
- Calculate ROI if hypothetically following alert

Output:
- Probability of profitable trade (0-1)
- Use as confidence score
"""

class MLConfidenceScorer:
    async def predict_confidence(
        self,
        alert: Alert,
        features: dict
    ) -> Decimal:
        pass
```

#### 12.2 Backtest Framework
```python
"""
Backtest signal performance on historical data.

Process:
1. Load historical trades from DB
2. Run signal detectors on each trade
3. Track outcomes (market resolutions)
4. Calculate metrics:
   - Precision: % of alerts that were profitable
   - Recall: % of profitable trades detected
   - ROI: Return if following all alerts
   - Sharpe ratio

Use for:
- Tuning signal parameters
- Evaluating new signals
- A/B testing signal changes
"""

class SignalBacktester:
    async def backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        signals: list[SignalDetector]
    ) -> dict:
        pass
```

---

### 13. Advanced Analytics

**Новый модуль:** `scanner/analytics/`

#### 13.1 Market Impact Analysis
```python
"""
Analyze how trades impact market prices.

Metrics:
- Price impact: Δprice per $1000 traded
- Order book depth at different price levels
- Liquidity absorption rate
- Time to price recovery

Use case: Identify whale trades that move markets
"""
```

#### 13.2 Wallet Network Analysis
```python
"""
Analyze relationships between wallets.

Techniques:
- On-chain funding analysis (same source)
- Co-trading patterns (same markets, same timing)
- Mirror trading detection
- Sybil attack detection

Visualization: Network graph of related wallets
"""
```

#### 13.3 Arbitrage Detection
```python
"""
Detect arbitrage opportunities across markets.

Types:
1. Related markets arbitrage:
   - "Trump wins election" vs "Republican wins"

2. Time-based arbitrage:
   - "Event happens by Dec" vs "Event happens by Jan"

3. Cross-market arbitrage:
   - Polymarket vs other prediction markets (Kalshi, etc.)
"""
```

---

### 14. Discord Bot

**Новый модуль:** `scanner/output/discord.py`

```python
"""
Discord bot for alerts (similar to Telegram).

Features:
- Embed messages with rich formatting
- Buttons for quick actions ("View Market", "View Wallet")
- Channel-based routing (high confidence → #high-priority)
- Roles/mentions for high-value alerts
- Slash commands:
  - /stats - Show scanner statistics
  - /wallet <address> - Lookup wallet profile
  - /market <id> - Lookup market info

Library: discord.py
"""
```

---

### 15. Web Dashboard

**Новый модуль:** `scanner/web/`

```python
"""
Web dashboard for monitoring and configuration.

Tech stack:
- FastAPI backend
- React/Vue/Svelte frontend
- WebSocket for real-time updates

Features:
1. Live feed of trades and alerts
2. Statistics and charts
3. Wallet explorer
4. Market explorer
5. Configuration UI
6. Signal performance metrics
7. System health monitoring

Endpoints:
- GET /api/alerts - Recent alerts
- GET /api/trades - Recent trades
- GET /api/wallet/{address} - Wallet profile
- GET /api/market/{id} - Market details
- GET /api/stats - System statistics
- WS /ws/feed - Real-time trade/alert feed
"""
```

---

### 16. Historical Data Ingestion

**Новый модуль:** `scanner/ingestion/`

```python
"""
Backfill historical trades for analysis.

Process:
1. Fetch all historical trades from Polymarket APIs
2. Process through pipeline (filters, signals)
3. Store in database
4. Build wallet profiles from history
5. Calculate historical signal accuracy

Data sources:
- Polymarket Subgraph (complete history)
- CLOB API (recent trades)
- Archived data dumps

Use cases:
- Train ML models
- Backtest strategies
- Build wallet reputation system
"""

class HistoricalDataIngestion:
    async def ingest_historical_trades(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> None:
        pass
```

---

### 17. Notification Preferences

**Расширение:** `scanner/output/`

```python
"""
User-specific notification preferences.

Features:
- Minimum trade size per user
- Preferred market categories
- Minimum confidence score
- Notification frequency limits
- Quiet hours (no alerts at night)
- Webhook support for custom integrations

Database table: user_preferences
- user_id (Telegram ID or Discord ID)
- min_trade_size
- min_confidence
- excluded_categories
- max_alerts_per_hour
- quiet_hours_start
- quiet_hours_end
"""

class NotificationManager:
    async def should_send_alert(
        self,
        user_id: str,
        alert: Alert
    ) -> bool:
        """Check if alert matches user preferences."""
        pass
```

---

### 18. Multi-Chain Support

**Расширение для будущего**

```python
"""
Support other prediction markets and chains.

Potential integrations:
1. Kalshi (US regulated prediction market)
2. Augur (Ethereum-based)
3. Azuro (Sports betting on-chain)
4. Polymarket on other chains if they expand

Architecture changes:
- Abstract MarketProtocol interface
- Chain-specific transport layers
- Unified data models
- Cross-chain arbitrage detection
"""
```

---

## 📋 ПРИОРИТИЗАЦИЯ

### Sprint 1 (2-3 недели): Core Production Features
- [ ] WalletService real API integration
- [ ] Database layer (PostgreSQL + schema)
- [ ] Cache layer (Redis)
- [ ] Rate limiting + retry logic
- [ ] Structured logging
- [ ] Basic monitoring (health checks)

### Sprint 2 (2-3 недели): Reliability & Observability
- [ ] Circuit breaker pattern
- [ ] Prometheus metrics
- [ ] Error tracking (Sentry)
- [ ] Alert enrichment improvements
- [ ] MarketService enhancements
- [ ] Unit tests (>80% coverage)

### Sprint 3 (2-3 недели): Advanced Signals
- [ ] Real OddsMovementDetector
- [ ] Enhanced ClusteringDetector
- [ ] TimingDetector with events API
- [ ] Real ContrarianDetector
- [ ] Signal backtesting framework

### Sprint 4 (1-2 недели): Deployment & Operations
- [ ] CI/CD pipeline
- [ ] Docker production setup
- [ ] Kubernetes manifests
- [ ] Deployment automation
- [ ] Runbooks and documentation

### Sprint 5+ (Ongoing): Advanced Features
- [ ] ML confidence scoring
- [ ] Discord bot
- [ ] Web dashboard
- [ ] Historical data ingestion
- [ ] Advanced analytics

---

## 🔒 БЕЗОПАСНОСТЬ

### Обязательные меры:

1. **Secrets Management**
   - Never commit private keys or API tokens
   - Use environment variables or secret managers
   - Rotate secrets regularly

2. **API Security**
   - Rate limiting to prevent abuse
   - Input validation on all external data
   - SQL injection prevention (use parameterized queries)

3. **Network Security**
   - Use HTTPS for all API calls
   - Validate SSL certificates
   - Don't expose internal ports

4. **Database Security**
   - Encrypted connections
   - Read-only replicas for analytics
   - Regular backups
   - Row-level security if multi-tenant

5. **Monitoring Security**
   - Alert on failed authentication attempts
   - Alert on unusual API usage patterns
   - Log all security events

---

## 📚 ДОКУМЕНТАЦИЯ

### Необходимая документация:

1. **README.md** - ✅ Готово
2. **API.md** - API documentation for external integrations
3. **ARCHITECTURE.md** - System architecture and design decisions
4. **DEPLOYMENT.md** - ✅ Готово (базовая версия)
5. **CONTRIBUTING.md** - Guidelines for contributors
6. **RUNBOOK.md** - Operational procedures
7. **TROUBLESHOOTING.md** - Common issues and solutions
8. **SIGNALS.md** - Detailed explanation of each signal detector
9. **DATABASE.md** - Database schema and queries
10. **API_CLIENTS.md** - How to use Polymarket APIs

---

## 🎯 ИТОГО

**Текущее состояние:** MVP с моковыми данными, работает для демонстрации концепции

**Для Production нужно:**
- ✅ 18 крупных компонентов
- ✅ ~50+ новых методов и API интеграций
- ✅ Полноценная инфраструктура (БД, кэш, мониторинг)
- ✅ Тесты и CI/CD
- ✅ Документация

**Оценка трудозатрат:** 8-12 недель работы для одного разработчика

**Критический путь:** Database → Real APIs → Caching → Monitoring → Testing → Deployment

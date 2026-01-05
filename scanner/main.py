"""Main entry point for the Polymarket scanner."""

import asyncio
import logging
import signal
import sys
from decimal import Decimal

from scanner.config import config
from scanner.filters import LPFilter, MarketFilter, SizeFilter
from scanner.output import ConsoleOutput, TelegramOutput
from scanner.pipeline import Pipeline
from scanner.services import AlertEnricher, MarketService, WalletService
from scanner.signals import (
    ClusteringDetector,
    ContrarianDetector,
    FreshWalletDetector,
    OddsMovementDetector,
    SizeAnomalyDetector,
    TimingDetector,
)
from scanner.transport import MockTradeGenerator, PolymarketCLOBClient, PolymarketRESTPoller


def setup_logging() -> None:
    """Configure logging for the application."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Reduce noise from external libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def create_pipeline(use_mock: bool = True) -> Pipeline:
    """
    Create and configure the processing pipeline.

    Args:
        use_mock: Whether to use mock data instead of real WebSocket.

    Returns:
        Configured Pipeline instance.
    """
    # Create services
    wallet_service = WalletService()
    market_service = MarketService()

    # Create signal detectors
    signal_detectors = [
        FreshWalletDetector(config),
        SizeAnomalyDetector(config),
        TimingDetector(),
        OddsMovementDetector(),
        ContrarianDetector(),
        ClusteringDetector(config),
    ]

    # Create enricher
    enricher = AlertEnricher(
        wallet_service=wallet_service,
        market_service=market_service,
        signal_detectors=signal_detectors,
    )

    # Create filters
    # NOTE: Filters disabled for debugging - uncomment when trades are flowing
    filters = [
        # MarketFilter(config),  # Фильтр по категориям
        SizeFilter(config),    # Фильтр по размеру ($2000+)
        # LPFilter(config),      # Фильтр LP
    ]

    # Create outputs
    outputs = [
        ConsoleOutput(use_colors=True),
    ]

    # Add Telegram output if configured
    if config.telegram_bot_token and config.telegram_chat_id:
        outputs.append(
            TelegramOutput(
                bot_token=config.telegram_bot_token,
                chat_id=config.telegram_chat_id,
                enabled=config.telegram_enabled,
            )
        )

    # Create data source
    if use_mock:
        source = MockTradeGenerator(
            trades_per_minute=20,  # Generate ~20 trades per minute
            min_size=Decimal("500"),
            max_size=Decimal("100000"),
            large_trade_probability=0.15,
        )
    elif config.private_key:
        # Use authenticated CLOB client if private key is provided
        source = PolymarketCLOBClient(
            config=config,
            poll_interval=3.0,
        )
    else:
        # Use REST poller for public data (limited functionality)
        source = PolymarketRESTPoller(
            config=config,
            poll_interval=5.0,
        )

    return Pipeline(
        source=source,
        filters=filters,
        enricher=enricher,
        outputs=outputs,
    )


async def run_scanner(use_mock: bool = True) -> None:
    """
    Run the scanner.

    Args:
        use_mock: Whether to use mock data.
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Polymarket Trade Scanner")
    logger.info("=" * 60)
    if use_mock:
        mode = "MOCK"
    elif config.private_key:
        mode = "LIVE (authenticated CLOB API)"
    else:
        mode = "LIVE (public API - limited)"
    logger.info(f"Mode: {mode}")
    logger.info(f"Min trade size: ${config.min_trade_size_usd:,}")
    logger.info(f"Excluded categories: {[c.value for c in config.excluded_categories]}")
    if config.telegram_bot_token and config.telegram_chat_id and config.telegram_enabled:
        telegram_status = "enabled"
    elif not config.telegram_enabled:
        telegram_status = "disabled (SCANNER_TELEGRAM_ENABLED=false)"
    elif not config.telegram_bot_token:
        telegram_status = "disabled (no bot token)"
    elif not config.telegram_chat_id:
        telegram_status = "disabled (no chat ID)"
    else:
        telegram_status = "disabled"
    logger.info(f"Telegram notifications: {telegram_status}")
    logger.info("=" * 60)

    pipeline = create_pipeline(use_mock=use_mock)

    # Handle graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Shutdown signal received")
        shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Run pipeline
    try:
        pipeline_task = asyncio.create_task(pipeline.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [pipeline_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.error(f"Scanner error: {e}")
        raise
    finally:
        logger.info("Scanner stopped")
        logger.info(f"Final stats: {pipeline.stats}")


def main() -> None:
    """Main entry point."""
    setup_logging()

    # Check for --live flag
    use_mock = "--live" not in sys.argv

    try:
        asyncio.run(run_scanner(use_mock=use_mock))
    except KeyboardInterrupt:
        print("\nShutdown complete.")


if __name__ == "__main__":
    main()


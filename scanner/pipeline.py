"""Trade processing pipeline."""

import logging
from collections.abc import AsyncIterator
from typing import Protocol

from scanner.domain.models import Alert, Trade
from scanner.filters.base import TradeFilter
from scanner.output.base import AlertOutput
from scanner.services.enrichment import AlertEnricher


logger = logging.getLogger(__name__)


class TradeSource(Protocol):
    """Protocol for trade data sources."""

    async def trades(self) -> AsyncIterator[Trade]:
        """Yield trades from the source."""
        ...


class Pipeline:
    """
    Main trade processing pipeline.

    Flow:
    Trade Source → Filters → Enrichment → Signal Detection → Output

    Each component is pluggable and can be enabled/disabled.
    """

    def __init__(
        self,
        source: TradeSource,
        filters: list[TradeFilter],
        enricher: AlertEnricher,
        outputs: list[AlertOutput],
    ):
        """
        Initialize pipeline.

        Args:
            source: Trade data source (WebSocket or mock).
            filters: List of filters to apply.
            enricher: Alert enricher for signal detection.
            outputs: List of output handlers.
        """
        self._source = source
        self._filters = [f for f in filters if f.enabled]
        self._enricher = enricher
        self._outputs = [o for o in outputs if o.enabled]

        # Statistics
        self._stats = {
            "trades_received": 0,
            "trades_filtered": 0,
            "alerts_generated": 0,
            "filter_rejections": {},
        }

    async def run(self) -> None:
        """
        Run the pipeline, processing trades as they arrive.

        This method runs indefinitely until cancelled.
        """
        logger.info("Pipeline started")
        logger.info(f"Active filters: {[f.name for f in self._filters]}")
        logger.info(f"Active outputs: {len(self._outputs)}")

        try:
            async for trade in self._source.trades():
                await self._process_trade(trade)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            raise
        finally:
            logger.info("Pipeline stopped")
            self._log_stats()

    async def _process_trade(self, trade: Trade) -> None:
        """
        Process a single trade through the pipeline.

        Args:
            trade: Trade to process.
        """
        self._stats["trades_received"] += 1

        # Apply filters
        for filter_ in self._filters:
            try:
                result = await filter_.check(trade)

                if not result.passed:
                    self._stats["trades_filtered"] += 1
                    self._stats["filter_rejections"][filter_.name] = (
                        self._stats["filter_rejections"].get(filter_.name, 0) + 1
                    )
                    logger.debug(
                        f"Trade {trade.id} rejected by {filter_.name}: {result.reason}"
                    )
                    return

            except Exception as e:
                logger.error(f"Filter {filter_.name} error: {e}")
                # Continue with other filters on error

        # Trade passed all filters - enrich it
        try:
            alert = await self._enricher.enrich(trade)

            if alert:
                self._stats["alerts_generated"] += 1
                await self._send_alert(alert)

        except Exception as e:
            logger.error(f"Enrichment error for trade {trade.id}: {e}")

    async def _send_alert(self, alert: Alert) -> None:
        """
        Send alert to all outputs.

        Args:
            alert: Alert to send.
        """
        for output in self._outputs:
            try:
                await output.send(alert)
            except Exception as e:
                logger.error(f"Output error: {e}")

    def _log_stats(self) -> None:
        """Log pipeline statistics."""
        logger.info("Pipeline statistics:")
        logger.info(f"  Trades received: {self._stats['trades_received']}")
        logger.info(f"  Trades filtered: {self._stats['trades_filtered']}")
        logger.info(f"  Alerts generated: {self._stats['alerts_generated']}")

        if self._stats["filter_rejections"]:
            logger.info("  Filter rejections:")
            for name, count in self._stats["filter_rejections"].items():
                logger.info(f"    {name}: {count}")

    @property
    def stats(self) -> dict:
        """Get pipeline statistics."""
        return self._stats.copy()


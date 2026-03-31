"""
Trades buffer service (WebSocket -> in-memory deque).

Rationale:
- Current exchange adapters expose `subscribe_trades` but do not provide a unified
  REST `get_trades` interface.
- For "everything_live" (including trades) we subscribe via WebSocket and keep
  a rolling buffer of the most recent N trades in memory.

This design avoids heavy Redis list operations and keeps the first iteration
simple. A future improvement can persist to Redis for multi-worker scenarios.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Deque, Dict, List, Tuple

from loguru import logger

from app.datafeeds.runtime import datafeed_manager


@dataclass
class TradeCacheItem:
    """A single standardized trade record for live calculations."""

    exchange: str
    symbol: str
    market_type: str
    trade_id: str
    price: float
    quantity: float
    side: str
    event_time: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for downstream DataFrame creation."""
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "trade_id": self.trade_id,
            "price": self.price,
            "quantity": self.quantity,
            "side": self.side,
            "event_time": self.event_time,
        }


class TradesBufferService:
    """
    Maintain rolling in-memory buffers of recent trades.

    Buffers are keyed by (exchange, symbol, market_type).
    On-demand subscriptions are created on first use.
    """

    def __init__(self, maxlen: int = 500) -> None:
        """
        Args:
            maxlen: Maximum trades kept per key.
        """
        self._maxlen = maxlen
        self._buffers: Dict[Tuple[str, str, str], Deque[TradeCacheItem]] = {}
        self._events: Dict[Tuple[str, str, str], asyncio.Event] = {}
        self._subscribed: set[Tuple[str, str, str]] = set()
        self._lock = asyncio.Lock()

    def _get_key(self, exchange: str, symbol: str, market_type: str) -> Tuple[str, str, str]:
        """Create a stable key tuple."""
        return (exchange, symbol, market_type)

    async def _ensure_subscription(
        self,
        exchange: str,
        symbol: str,
        market_type: str,
    ) -> None:
        """
        Ensure we are subscribed to the trades stream for the given key.

        Notes:
            BinanceAdapter.subscribe_trades subscribes for both spot/perp inside
            adapter level; UnifiedTrade includes market_type, so the callback can
            be used for different streams.
        """
        key = self._get_key(exchange, symbol, market_type)
        async with self._lock:
            if key in self._subscribed:
                return

            if key not in self._buffers:
                self._buffers[key] = deque(maxlen=self._maxlen)
            if key not in self._events:
                self._events[key] = asyncio.Event()

            async def callback(unified_trade: Any) -> None:
                try:
                    # UnifiedTrade is a dataclass: exchange/symbol/market_type fields
                    ut = unified_trade
                    if (
                        ut.exchange != exchange
                        or ut.symbol != symbol
                        or ut.market_type != market_type
                    ):
                        return

                    item = TradeCacheItem(
                        exchange=str(ut.exchange),
                        symbol=str(ut.symbol),
                        market_type=str(ut.market_type),
                        trade_id=str(ut.trade_id),
                        price=float(ut.price),
                        quantity=float(ut.quantity),
                        side=str(ut.side),
                        event_time=ut.event_time,
                    )
                    self._buffers[key].append(item)
                    # Mark ready after receiving first trade.
                    self._events[key].set()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("trade buffer callback error: %s", exc, exc_info=True)

            # DatafeedManager.subscribe expects a normal callable callback.
            # Our callback is async; wrap it to ensure it works for adapters that call synchronously.
            def sync_callback(ut: Any) -> None:
                asyncio.create_task(callback(ut))

            await datafeed_manager.subscribe(
                exchange_name=exchange,
                stream_type="trades",
                symbol=symbol,
                callback=sync_callback,
            )
            self._subscribed.add(key)
            logger.info("已订阅 trades：%s", key)

    async def get_recent_trades(
        self,
        exchange: str,
        symbol: str,
        market_type: str,
        limit: int = 200,
        timeout_seconds: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """
        Get recent trades from in-memory buffer.

        Args:
            exchange: Exchange id (e.g. binance)
            symbol: Trading pair (e.g. BTCUSDT)
            market_type: spot/perp
            limit: Return at most N trades (newest first)
            timeout_seconds: Wait for first trade before giving up.

        Returns:
            List of dicts: {trade_id, price, quantity, side, event_time, ...}
        """
        key = self._get_key(exchange, symbol, market_type)
        await self._ensure_subscription(exchange, symbol, market_type)

        # Wait for at least one trade (best-effort).
        event = self._events.get(key)
        if event and not event.is_set():
            try:
                await asyncio.wait_for(event.wait(), timeout_seconds)
            except asyncio.TimeoutError:
                pass

        buf = self._buffers.get(key)
        if not buf:
            return []

        # newest first for consistency with DB queries used elsewhere
        items = list(buf)[-limit:][::-1]
        return [it.to_dict() for it in items]


trades_buffer_service = TradesBufferService()


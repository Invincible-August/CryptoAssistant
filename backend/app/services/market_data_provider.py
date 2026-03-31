"""
MarketDataProvider - unified exchange data access with cache/live switching.

This provider is the foundation for the requirement:
  "图表和数据需求从币安/OKX/Bitget 路径获取；可自由选择，但一次只用一个。"

Current implementation supports:
  - Binance adapter (live via DatafeedManager + BinanceAdapter)
  - Cache via existing DB/Redis (market_service)

Live trade data uses an in-memory WebSocket buffer to avoid extending adapter
interfaces for REST trades.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Sequence

import pandas as pd
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.datafeeds.runtime import datafeed_manager
from app.services.trades_buffer_service import trades_buffer_service
from app.services import market_service


SourceMode = Literal["cache", "live"]


def _parse_iso_datetime(dt: Any) -> datetime:
    """Parse ISO datetime string to datetime (naive UTC is preserved)."""
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, str):
        return datetime.fromisoformat(dt)
    raise ValueError(f"Invalid datetime value: {dt!r}")


def _to_float(x: Any) -> float:
    """Convert Decimal/str/number to float safely."""
    if x is None:
        return 0.0
    return float(x)


@dataclass(frozen=True)
class KlineDict:
    """A plain dict schema for kline sequences used by indicator calculations."""

    exchange: str
    symbol: str
    market_type: str
    interval: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exchange": self.exchange,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "interval": self.interval,
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trade_count": self.trade_count,
        }


class MarketDataProvider:
    """
    Unified data provider.

    Design:
      - cache mode reads from DB/Redis via `market_service`
      - live mode pulls from exchange adapter via `datafeed_manager`
      - for live mode, we can optionally persist pulled data back to DB to refresh cache
    """

    async def get_klines(
        self,
        db: AsyncSession,
        *,
        exchange: str,
        market_type: str,
        symbol: str,
        interval: str,
        limit: int = 500,
        source_mode: SourceMode = "cache",
        persist_to_db: bool = True,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get historical klines as a list of dicts.

        Args:
            db: Async SQLAlchemy session.
            exchange: Exchange id (e.g. binance).
            market_type: spot or futures.
            symbol: Trading pair (e.g. BTCUSDT).
            interval: Kline interval (e.g. 1m, 1h).
            limit: Max number of klines to load.
            source_mode: cache => read from DB/Redis, live => pull from exchange adapter.
            persist_to_db: In live mode, whether to persist fetched klines to DB to warm cache.
            use_proxy: In live mode, whether to route exchange REST requests through local HTTP proxy (if supported).

        Returns:
            List[dict] where each dict contains open_time/high/low/close/volume etc.
        """
        if source_mode == "cache":
            orm_klines = await market_service.get_klines(
                db=db,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                interval=interval,
                limit=limit,
            )
            return [
                {
                    "open_time": k.open_time,
                    "open": float(k.open) if k.open is not None else 0.0,
                    "high": float(k.high) if k.high is not None else 0.0,
                    "low": float(k.low) if k.low is not None else 0.0,
                    "close": float(k.close) if k.close is not None else 0.0,
                    "volume": float(k.volume) if k.volume is not None else 0.0,
                    "quote_volume": float(k.quote_volume)
                    if k.quote_volume is not None
                    else 0.0,
                    "trade_count": k.trade_count or 0,
                }
                for k in orm_klines
            ]

        # ---- live mode ----
        adapter = datafeed_manager.get_adapter(exchange)
        if not adapter:
            raise ValueError(f"交易所适配器未注册: {exchange}")

        # For live mode: some exchanges (e.g. Binance) may require a local HTTP proxy.
        # We call with `use_proxy` only when the adapter supports it.
        try:
            raw = await adapter.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                use_proxy=use_proxy,
            )
        except TypeError:
            # Fallback for adapters that do not accept `use_proxy`.
            raw = await adapter.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
            )

        klines: List[Dict[str, Any]] = []
        for k in raw:
            open_time = _parse_iso_datetime(k.get("open_time"))
            close_time = _parse_iso_datetime(k.get("close_time"))
            market_type_out = k.get("market_type") or market_type

            klines.append(
                KlineDict(
                    exchange=k["exchange"],
                    symbol=k["symbol"],
                    market_type=market_type_out,
                    interval=k["interval"],
                    open_time=open_time,
                    close_time=close_time,
                    open=_to_float(k.get("open")),
                    high=_to_float(k.get("high")),
                    low=_to_float(k.get("low")),
                    close=_to_float(k.get("close")),
                    volume=_to_float(k.get("volume")),
                    quote_volume=_to_float(k.get("quote_volume")),
                    trade_count=int(k.get("trade_count") or 0),
                ).to_dict()
            )

        if persist_to_db:
            # Persist to DB so cache becomes warm for subsequent cache-mode requests.
            # For MVP we do a simple loop; later we can optimize with bulk upsert.
            for k in klines:
                await market_service.save_kline(db, k)

        return [
            {
                "open_time": k["open_time"],
                "open": k["open"],
                "high": k["high"],
                "low": k["low"],
                "close": k["close"],
                "volume": k["volume"],
                "quote_volume": k["quote_volume"],
                "trade_count": k.get("trade_count", 0),
            }
            for k in klines
        ]

    async def get_orderbook(
        self,
        db: AsyncSession,
        *,
        exchange: str,
        market_type: str,
        symbol: str,
        source_mode: SourceMode = "cache",
        persist_to_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Get orderbook snapshot for factor computations.

        Returns:
            {"bids": [...], "asks": [...], "snapshot_time": str|None}
        """
        if source_mode == "cache":
            snapshot = await market_service.get_latest_orderbook(
                db=db,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
            )
            if not snapshot:
                return {"bids": [], "asks": [], "snapshot_time": None}
            return {
                "bids": snapshot.bids_json or [],
                "asks": snapshot.asks_json or [],
                "snapshot_time": str(snapshot.snapshot_time),
            }

        adapter = datafeed_manager.get_adapter(exchange)
        if not adapter:
            raise ValueError(f"交易所适配器未注册: {exchange}")

        ob = await adapter.get_orderbook(symbol=symbol, limit=20)
        # persist (optional) so cache mode can read later
        if persist_to_db:
            # Adapter provides ISO strings; DB model expects datetime objects.
            ob_to_save = dict(ob)
            if ob_to_save.get("snapshot_time"):
                ob_to_save["snapshot_time"] = _parse_iso_datetime(
                    ob_to_save["snapshot_time"]
                )
            await market_service.save_orderbook_snapshot(db, ob_to_save)

        return {
            "bids": ob.get("bids") or [],
            "asks": ob.get("asks") or [],
            "snapshot_time": ob.get("snapshot_time"),
        }

    async def get_open_interest(
        self,
        db: AsyncSession,
        *,
        exchange: str,
        market_type: str,
        symbol: str,
        source_mode: SourceMode = "cache",
        persist_to_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Get open interest for factor computations.

        Returns:
            {"open_interest": float, "event_time": str|None}
        """
        # open_interest cache path
        if source_mode == "cache":
            oi = await market_service.get_latest_oi(
                db=db,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
            )
            if not oi:
                return {"open_interest": 0.0, "event_time": None}
            return {"open_interest": float(oi.open_interest), "event_time": str(oi.event_time)}

        adapter = datafeed_manager.get_adapter(exchange)
        if not adapter:
            raise ValueError(f"交易所适配器未注册: {exchange}")

        oi_dict = await adapter.get_open_interest(symbol=symbol)
        if persist_to_db:
            oi_to_save = dict(oi_dict)
            if oi_to_save.get("event_time"):
                oi_to_save["event_time"] = _parse_iso_datetime(
                    oi_to_save["event_time"]
                )
            await market_service.save_open_interest(db, oi_to_save)

        return {
            "open_interest": _to_float(oi_dict.get("open_interest")),
            "event_time": oi_dict.get("event_time"),
        }

    async def get_funding_rate(
        self,
        db: AsyncSession,
        *,
        exchange: str,
        symbol: str,
        source_mode: SourceMode = "cache",
        persist_to_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Get latest funding rate.

        Returns:
            {"funding_rate": float, "funding_time": str|None}
        """
        if source_mode == "cache":
            funding = await market_service.get_latest_funding(
                db=db,
                exchange=exchange,
                symbol=symbol,
            )
            if not funding:
                return {"funding_rate": 0.0, "funding_time": None}
            return {
                "funding_rate": float(funding.funding_rate),
                "funding_time": str(funding.funding_time),
            }

        adapter = datafeed_manager.get_adapter(exchange)
        if not adapter:
            raise ValueError(f"交易所适配器未注册: {exchange}")

        fd = await adapter.get_funding_rate(symbol=symbol)
        if persist_to_db:
            fd_to_save = dict(fd)
            if fd_to_save.get("funding_time"):
                fd_to_save["funding_time"] = _parse_iso_datetime(
                    fd_to_save["funding_time"]
                )
            await market_service.save_funding(db, fd_to_save)

        return {
            "funding_rate": _to_float(fd.get("funding_rate")),
            "funding_time": fd.get("funding_time"),
        }

    async def get_trades(
        self,
        db: AsyncSession,
        *,
        exchange: str,
        market_type: str,
        symbol: str,
        limit: int = 200,
        source_mode: SourceMode = "cache",
    ) -> List[Dict[str, Any]]:
        """
        Get recent trades for factor computations.

        Returns:
            List[dict] for DataFrame creation.
        """
        if source_mode == "cache":
            trades = await market_service.get_recent_trades(
                db=db,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                limit=limit,
            )
            return [
                {
                    "trade_id": t.trade_id,
                    "price": float(t.price) if t.price is not None else 0.0,
                    "quantity": float(t.quantity) if t.quantity is not None else 0.0,
                    "side": t.side,
                    "event_time": t.event_time,
                }
                for t in trades
            ]

        # live mode - from in-memory WS buffer
        return await trades_buffer_service.get_recent_trades(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            limit=limit,
        )


market_data_provider = MarketDataProvider()


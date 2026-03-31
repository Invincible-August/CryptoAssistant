"""
Chart bundle service: K线 + 可选技术指标，输出 Lightweight Charts 兼容 JSON。

Designed for the chart analysis page: computes indicators in-memory (no IndicatorResult
persistence) to avoid flooding the database on each chart refresh.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.indicators.registry import indicator_registry
from app.services.chart_series_builder import build_indicator_chart_payloads
from app.services.market_data_provider import market_data_provider, SourceMode
from app.services.plugin_runtime_service import get_plugin_runtime_service
from app.lightweight_charts_compat.chart_mapping import (
    build_chart_config,
    klines_to_tv_format,
)


async def build_lightweight_chart_bundle(
    db: AsyncSession,
    *,
    exchange: str,
    market_type: str,
    symbol: str,
    timeframe: str,
    limit: int = 500,
    indicator_keys: Optional[Sequence[str]] = None,
    theme: str = "dark",
    source_mode: SourceMode = "cache",
    use_proxy: bool = False,
) -> Dict[str, Any]:
    """
    Load K线 from DB, optionally compute indicators, return a frontend-ready bundle.

    Args:
        db: Database session.
        exchange: Exchange id (e.g. binance).
        market_type: spot or futures.
        symbol: Trading pair (e.g. BTCUSDT).
        timeframe: Kline interval (e.g. 1h).
        limit: Max klines to load (ascending by time).
        indicator_keys: Zero or more registered indicator keys; None or empty = candles only.
        theme: dark or light chart theme.
        use_proxy: When true and `source_mode` is `live`, route Binance REST K-line requests through HTTP proxy.

    Returns:
        Dict with keys: config, candlestick, overlays, subcharts, meta.

    Raises:
        ValueError: No kline data available for the symbol/timeframe.
    """
    klines = await market_data_provider.get_klines(
        db,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        interval=timeframe,
        limit=limit,
        source_mode=source_mode,
        persist_to_db=(source_mode == "live"),
        use_proxy=use_proxy,
    )

    if not klines:
        raise ValueError(
            f"没有K线数据: {exchange} {symbol} {market_type} {timeframe}，请先导入或采集行情"
        )

    # Provider already returns the dict schema needed by klines_to_tv_format().
    candlestick = klines_to_tv_format(klines)
    chart_config = build_chart_config(symbol=symbol, interval=timeframe, theme=theme)

    overlays: List[Dict[str, Any]] = []
    subcharts: List[Dict[str, Any]] = []
    runtime = get_plugin_runtime_service()

    kline_df = pd.DataFrame(
        [
            {
                "open_time": k["open_time"],
                "open": k["open"],
                "high": k["high"],
                "low": k["low"],
                "close": k["close"],
                "volume": k.get("volume", 0.0),
                "quote_volume": k.get("quote_volume", 0.0),
                "trade_count": k.get("trade_count", 0),
            }
            for k in klines
        ]
    )

    keys = [k.strip() for k in (indicator_keys or []) if k and str(k).strip()]
    failed: List[Dict[str, str]] = []

    for ind_key in keys:
        try:
            if not runtime.is_indicator_load_enabled(ind_key):
                failed.append({"indicator_key": ind_key, "reason": "disabled_by_runtime"})
                continue
            try:
                ind_cls = indicator_registry.get(ind_key)
            except KeyError:
                failed.append({"indicator_key": ind_key, "reason": "unknown_indicator_key"})
                continue
            validated = ind_cls.validate_params({})
            result_df = ind_cls.calculate(kline_df, validated)
            ov, sub = build_indicator_chart_payloads(
                ind_cls, ind_key, result_df, validated
            )
            overlays.extend(ov)
            subcharts.extend(sub)
        except Exception as exc:  # noqa: BLE001 — collect per-indicator errors for API
            logger.warning("指标计算失败 [%s]: %s", ind_key, exc)
            failed.append({"indicator_key": ind_key, "reason": str(exc)})

    return {
        "config": chart_config,
        "candlestick": candlestick,
        "overlays": overlays,
        "subcharts": subcharts,
        "markers": [],
        "meta": {
            "symbol": symbol,
            "timeframe": timeframe,
            "exchange": exchange,
            "market_type": market_type,
            "klines_loaded": len(klines),
            "source_mode": source_mode,
            "indicators_requested": list(keys),
            "failed_indicators": failed,
        },
    }

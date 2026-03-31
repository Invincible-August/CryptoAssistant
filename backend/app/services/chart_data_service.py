"""
Chart bundle service: K线 + 可选技术指标，输出 Lightweight Charts 兼容 JSON。

Designed for the chart analysis page: computes indicators in-memory (no IndicatorResult
persistence) to avoid flooding the database on each chart refresh.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.indicators.registry import indicator_registry
from app.services.chart_series_builder import build_indicator_chart_payloads
from app.services.kline_aggregation import aggregate_1m_klines_to_timeframe
from app.services.kline_backfill_service import backfill_binance_1m_last_7d
from app.services.market_data_provider import market_data_provider, SourceMode
from app.services import market_service
from app.services.plugin_runtime_service import get_plugin_runtime_service
from app.lightweight_charts_compat.chart_mapping import (
    build_chart_config,
    klines_to_tv_format,
)
from app.utils.time import remove_tz


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
    # 说明（按 spec）：
    # - cache 模式：保持原有逻辑不变（从 DB/Redis 读取目标周期）
    # - live 模式：必须显式回补最近 7 天 1m 入库，然后按固定 7 天窗读库 1m，
    #   再聚合到目标周期并按 limit 截断输出。
    if source_mode == "live":
        if exchange != "binance":
            # 说明：当前回补服务仅实现 Binance 1m 回补；为了不影响其他交易所的旧行为，
            # 这里对非 Binance 仍走原有 live 拉取路径（不改 cache 逻辑）。
            klines = await market_data_provider.get_klines(
                db,
                exchange=exchange,
                market_type=market_type,
                symbol=symbol,
                interval=timeframe,
                limit=limit,
                source_mode=source_mode,
                persist_to_db=True,
                use_proxy=use_proxy,
            )
            aggregation_meta: Dict[str, Any] = {"dropped_total": 0}
            backfill_window_days = 7
            aggregation_source_interval = "1m"
        else:
            # 1) 显式触发回补：只拉 1m，严格 7 天窗口（闭开语义在回补服务内实现）
            backfill_result = await backfill_binance_1m_last_7d(
                db,
                symbol=symbol,
                market_type=market_type,  # spot / perp
                use_proxy=use_proxy,
            )

            # 2) 以回补服务返回的窗口为准，按固定 7 天窗从 DB 读取 1m（闭开语义）
            window_start = remove_tz(datetime.fromisoformat(backfill_result["start"]))
            window_end_exclusive = remove_tz(
                datetime.fromisoformat(backfill_result["end_exclusive"])
            )

            # 说明：7 天 1m 理论最大 10080 根；考虑极端情况下时间对齐/闰秒等防御，给一点冗余。
            window_limit = 11000
            orm_klines_1m = await market_service.get_klines(
                db=db,
                exchange=exchange,
                symbol=symbol,
                market_type=market_type,
                interval="1m",
                start_time=window_start,
                end_exclusive=window_end_exclusive,
                limit=window_limit,
            )

            klines_1m: List[Dict[str, Any]] = [
                {
                    "open_time": k.open_time,
                    "close_time": k.close_time,
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
                for k in orm_klines_1m
            ]

            # 3) 聚合：统一走聚合器（即使 timeframe=1m，也能拿到 dropped_total）
            aggregated, aggregation_meta = aggregate_1m_klines_to_timeframe(
                klines_1m, timeframe
            )

            # 4) limit 截断：聚合后再截断，保持时间升序输出（取最近 limit 根）
            if limit and limit > 0:
                aggregated = aggregated[-limit:]

            klines = aggregated
            backfill_window_days = 7
            aggregation_source_interval = "1m"
    else:
        klines = await market_data_provider.get_klines(
            db,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            interval=timeframe,
            limit=limit,
            source_mode=source_mode,
            persist_to_db=False,
            use_proxy=use_proxy,
        )
        aggregation_meta = {"dropped_total": 0}
        backfill_window_days = 7
        aggregation_source_interval = "1m"

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
            # --- live 7d backfill + 1m aggregation meta（按 spec 增加，保留原有字段） ---
            "backfill_window_days": backfill_window_days,
            "aggregation_source_interval": aggregation_source_interval,
            "dropped_total": int(aggregation_meta.get("dropped_total") or 0),
        },
    }

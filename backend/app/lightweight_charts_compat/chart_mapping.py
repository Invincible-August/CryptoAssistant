"""
Lightweight Charts chart/series mapping utilities.

This module converts internal K-line and indicator result shapes into the
JSON/shape consumed by the frontend `lightweight-charts` library.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger


def klines_to_tv_format(
    klines: List[Dict[str, Any]],
    price_precision: int = 8,
) -> List[Dict[str, Any]]:
    """
    Convert internal K-lines to Lightweight Charts candlestick format.

    Lightweight Charts expects:
        { "time": Unix seconds or "YYYY-MM-DD", "open": ..., "high": ..., "low": ..., "close": ... }

    We also include `volume` to support volume-related displays.
    """
    tv_klines: List[Dict[str, Any]] = []

    for kline in klines:
        timestamp = _to_unix_timestamp(kline.get("open_time"))
        if timestamp is None:
            logger.warning(
                "K线时间戳转换失败，跳过: %s", kline.get("open_time")
            )
            continue

        tv_klines.append(
            {
                "time": timestamp,
                "open": _to_float(kline.get("open"), price_precision),
                "high": _to_float(kline.get("high"), price_precision),
                "low": _to_float(kline.get("low"), price_precision),
                "close": _to_float(kline.get("close"), price_precision),
                "volume": _to_float(kline.get("volume"), 2),
            }
        )

    tv_klines.sort(key=lambda x: x["time"])
    return tv_klines


def indicator_to_tv_overlay(
    indicator_data: List[Dict[str, Any]],
    series_name: str,
    color: str = "#2196F3",
    line_width: int = 2,
) -> Dict[str, Any]:
    """
    Convert indicator series points to Lightweight Charts overlay (main chart).
    """
    formatted_data: List[Dict[str, Any]] = []

    for point in indicator_data:
        timestamp = _to_unix_timestamp(point.get("time"))
        value = point.get("value")

        if timestamp is None or value is None:
            continue

        formatted_data.append(
            {
                "time": timestamp,
                "value": _to_float(value, 8),
            }
        )

    formatted_data.sort(key=lambda x: x["time"])
    return {
        "name": series_name,
        "type": "line",
        "data": formatted_data,
        "options": {
            "color": color,
            "lineWidth": line_width,
            "priceLineVisible": False,
            "lastValueVisible": True,
            "crosshairMarkerVisible": True,
        },
    }


def indicator_to_tv_pane(
    indicator_data: List[Dict[str, Any]],
    series_name: str,
    chart_type: str = "histogram",
    color: str = "#26A69A",
) -> Dict[str, Any]:
    """
    Convert indicator series points to Lightweight Charts pane (sub chart).
    """
    formatted_data: List[Dict[str, Any]] = []

    for point in indicator_data:
        timestamp = _to_unix_timestamp(point.get("time"))
        value = point.get("value")

        if timestamp is None or value is None:
            continue

        data_point: Dict[str, Any] = {
            "time": timestamp,
            "value": _to_float(value, 8),
        }

        # histogram supports per-bar color (e.g., MACD bars)
        if chart_type == "histogram":
            point_color = point.get("color")
            if point_color:
                data_point["color"] = point_color

        formatted_data.append(data_point)

    formatted_data.sort(key=lambda x: x["time"])

    return {
        "name": series_name,
        "type": chart_type,
        "data": formatted_data,
        "options": {
            "color": color,
            "priceLineVisible": False,
            "lastValueVisible": True,
        },
    }


def markers_to_tv_format(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert trading signals to Lightweight Charts marker format.
    """
    markers: List[Dict[str, Any]] = []

    for signal in signals:
        timestamp = _to_unix_timestamp(signal.get("time"))
        if timestamp is None:
            continue

        direction = signal.get("direction", signal.get("action", "neutral")).lower()

        if direction in ("long", "buy"):
            markers.append(
                {
                    "time": timestamp,
                    "position": "belowBar",
                    "color": "#26A69A",
                    "shape": "arrowUp",
                    "text": signal.get("text", "买入"),
                }
            )
        elif direction in ("short", "sell"):
            markers.append(
                {
                    "time": timestamp,
                    "position": "aboveBar",
                    "color": "#EF5350",
                    "shape": "arrowDown",
                    "text": signal.get("text", "卖出"),
                }
            )
        else:
            markers.append(
                {
                    "time": timestamp,
                    "position": "aboveBar",
                    "color": "#FF9800",
                    "shape": "circle",
                    "text": signal.get("text", "平仓"),
                }
            )

    markers.sort(key=lambda x: x["time"])
    return markers


def build_chart_config(
    symbol: str,
    interval: str = "1h",
    theme: str = "dark",
) -> Dict[str, Any]:
    """
    Build frontend createChart() options and candlestick options.
    """
    dark_theme = {
        "background_color": "#1E1E2D",
        "text_color": "#D1D4DC",
        "grid_color": "rgba(42, 46, 57, 0.5)",
        "border_color": "#2A2E39",
        "crosshair_color": "#758696",
        "up_color": "#26A69A",
        "down_color": "#EF5350",
    }

    light_theme = {
        "background_color": "#FFFFFF",
        "text_color": "#333333",
        "grid_color": "rgba(200, 200, 200, 0.5)",
        "border_color": "#E0E0E0",
        "crosshair_color": "#888888",
        "up_color": "#26A69A",
        "down_color": "#EF5350",
    }

    colors = dark_theme if theme == "dark" else light_theme

    return {
        "symbol": symbol,
        "interval": interval,
        "chart_options": {
            "layout": {
                "background": {"type": "solid", "color": colors["background_color"]},
                "textColor": colors["text_color"],
            },
            "grid": {
                "vertLines": {"color": colors["grid_color"]},
                "horzLines": {"color": colors["grid_color"]},
            },
            "crosshair": {
                "mode": 0,
                "vertLine": {"color": colors["crosshair_color"]},
                "horzLine": {"color": colors["crosshair_color"]},
            },
            "timeScale": {
                "borderColor": colors["border_color"],
                "timeVisible": True,
                "secondsVisible": False,
            },
            "rightPriceScale": {
                "borderColor": colors["border_color"],
            },
        },
        "candlestick_options": {
            "upColor": colors["up_color"],
            "downColor": colors["down_color"],
            "borderUpColor": colors["up_color"],
            "borderDownColor": colors["down_color"],
            "wickUpColor": colors["up_color"],
            "wickDownColor": colors["down_color"],
        },
    }


_INDICATOR_CHART_MAP: Dict[str, Dict[str, Any]] = {
    "ma": {"display_type": "overlay", "default_color": "#FF9800", "line_width": 1},
    "ema": {"display_type": "overlay", "default_color": "#2196F3", "line_width": 1},
    "rsi": {"display_type": "pane", "chart_type": "line", "default_color": "#AB47BC"},
    "macd": {"display_type": "pane", "chart_type": "histogram", "default_color": "#26A69A"},
    "vwap": {"display_type": "overlay", "default_color": "#FFC107", "line_width": 2},
    "volume_spike": {
        "display_type": "pane",
        "chart_type": "histogram",
        "default_color": "#42A5F5",
    },
}


def get_indicator_chart_config(indicator_key: str) -> Dict[str, Any]:
    """
    Get default chart mapping configuration for an indicator key.
    """
    if indicator_key in _INDICATOR_CHART_MAP:
        return _INDICATOR_CHART_MAP[indicator_key]
    logger.debug("指标 '%s' 未在图表映射中注册，使用默认配置", indicator_key)
    return {
        "display_type": "overlay",
        "default_color": "#9E9E9E",
        "line_width": 1,
    }


def get_available_chart_indicators() -> Dict[str, Dict[str, Any]]:
    """
    Return all known indicator chart mappings.
    """
    return dict(_INDICATOR_CHART_MAP)


def _to_unix_timestamp(time_value: Any) -> Optional[int]:
    """
    Convert different time representations to Unix seconds.
    """
    if time_value is None:
        return None

    if isinstance(time_value, datetime):
        return int(time_value.timestamp())

    try:
        numeric_val = int(time_value)
        if numeric_val > 1_000_000_000_000:
            return numeric_val // 1000
        return numeric_val
    except (ValueError, TypeError):
        return None


def _to_float(value: Any, precision: int = 8) -> float:
    """
    Convert any numeric-like value to float with rounding.
    """
    if value is None:
        return 0.0
    try:
        return round(float(value), precision)
    except (ValueError, TypeError):
        return 0.0


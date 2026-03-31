"""
Lightweight Charts 图表/序列（series）映射工具。

本模块负责将后端内部的行情/指标/信号等数据结构，转换为前端 `lightweight-charts`
可直接消费的 JSON 结构（通常包含 `time`、`value` 或 OHLC 字段）。

为什么需要这层映射：
- 后端内部可能使用 `datetime`、`Decimal`、数据库 ORM 等结构；
- 前端渲染库通常要求更“扁平”的 JSON（时间戳 + 数值），且字段命名固定；
- 通过集中映射，可确保各页面/各服务返回的数据结构一致，减少前后端耦合与重复代码。

时间字段约定：
- `lightweight-charts` 的 `time` 支持 Unix 秒（int）或日期字符串（如 "YYYY-MM-DD"）。
- 本模块统一将可解析的时间转换为 **Unix 秒（int）**，以便前端时序排序与渲染。
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
    将内部 K 线列表转换为 Lightweight Charts 的蜡烛图（candlestick）数据格式。

    目标输出（每个元素）：
    - `time`: Unix 秒级时间戳（int）
    - `open/high/low/close`: 开高低收（float）
    - `volume`: 成交量（float），用于支持成交量相关展示（可选但本实现会填充）

    参数说明：
    - `klines`:
      - 类型：`List[Dict[str, Any]]`
      - 每个 kline dict 建议包含：
        - `open_time`: `datetime` / 秒级或毫秒级时间戳（int/str）/ 可被 `int(...)` 解析的值
        - `open/high/low/close/volume`: 数值（支持 `str/float/Decimal` 等）
      - 说明：若 `open_time` 无法转换为合法时间戳，会记录 warning 并跳过该条。
    - `price_precision`:
      - 类型：`int`
      - 默认：8
      - 说明：对 OHLC 价格进行 round 的小数位数；成交量固定保留 2 位。

    返回值：
    - 类型：`List[Dict[str, Any]]`
    - 说明：按 `time` 升序排序后的蜡烛图点列表。

    示例：

    ```python
    tv = klines_to_tv_format(
        klines=[{"open_time": datetime.utcnow(), "open": "1.0", "high": "1.2", "low": "0.9", "close": "1.1", "volume": "123.45"}],
        price_precision=4,
    )
    # tv[0] == {"time": 1710000000, "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 123.45}
    ```
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
    将指标序列点转换为 Lightweight Charts 的主图叠加线（overlay line series）。

    参数说明：
    - `indicator_data`:
      - 类型：`List[Dict[str, Any]]`
      - 每个点建议包含：
        - `time`: `datetime` / 秒级或毫秒级时间戳（int/str）
        - `value`: 数值（支持 `str/float/Decimal` 等）
      - 说明：`time` 或 `value` 缺失/不可解析时会跳过该点。
    - `series_name`:
      - 类型：`str`
      - 用途：前端展示用的序列名称（legend/tooltip 中可用）。
    - `color`:
      - 类型：`str`
      - 默认：`"#2196F3"`
      - 用途：线条颜色（CSS 色值）。
    - `line_width`:
      - 类型：`int`
      - 默认：2
      - 用途：线宽。

    返回值：
    - 类型：`Dict[str, Any]`
    - 结构：
      - `name`: 序列名称
      - `type`: `"line"`
      - `data`: `[{time, value}, ...]`（按 time 升序）
      - `options`: Lightweight Charts 线条配置（颜色/线宽/是否显示价格线等）

    示例：

    ```python
    overlay = indicator_to_tv_overlay(
        indicator_data=[{"time": 1710000000, "value": 123.4}],
        series_name="EMA(20)",
        color="#FF9800",
        line_width=1,
    )
    ```
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
    将指标序列点转换为 Lightweight Charts 的副图面板（pane/sub-chart）序列格式。

    常见用途：
    - RSI：副图 line
    - MACD：副图 histogram（柱状），并可对每根柱子指定颜色（多空柱）

    参数说明：
    - `indicator_data`:
      - 类型：`List[Dict[str, Any]]`
      - 每个点建议包含：
        - `time`: `datetime` / 秒级或毫秒级时间戳（int/str）
        - `value`: 数值
        - `color`（可选）: 当 `chart_type == "histogram"` 时，可给单个 bar 指定颜色
      - 说明：`time` 或 `value` 缺失/不可解析时会跳过该点。
    - `series_name`:
      - 类型：`str`
      - 用途：前端序列展示名。
    - `chart_type`:
      - 类型：`str`
      - 默认：`"histogram"`
      - 可选：`"histogram"`、`"line"`（以及 lightweight-charts 支持的其它类型）
      - 说明：当为 `"histogram"` 时支持每个点携带 `color` 覆盖。
    - `color`:
      - 类型：`str`
      - 默认：`"#26A69A"`
      - 用途：序列默认颜色（未提供单点 color 时使用）。

    返回值：
    - 类型：`Dict[str, Any]`
    - 结构同 `indicator_to_tv_overlay`，但 `type` 为 `chart_type`。
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
    将交易信号列表转换为 Lightweight Charts 的 marker（标记）格式。

    参数说明：
    - `signals`:
      - 类型：`List[Dict[str, Any]]`
      - 每个 signal dict 建议包含：
        - `time`: `datetime` / 秒级或毫秒级时间戳（int/str）
        - `direction`（可选）: `"long"|"buy"|"short"|"sell"|...`
          - 也支持从 `action` 字段兜底读取
        - `text`（可选）: marker 文本，默认：
          - long/buy → `"买入"`
          - short/sell → `"卖出"`
          - 其它 → `"平仓"`
      - 说明：`time` 不可解析会跳过该条信号。

    返回值：
    - 类型：`List[Dict[str, Any]]`
    - 每个 marker：
      - `time`: Unix 秒
      - `position`: `"belowBar"` / `"aboveBar"`
      - `color`: 颜色
      - `shape`: `"arrowUp"` / `"arrowDown"` / `"circle"`
      - `text`: 文本
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
    构建前端 `createChart()` 所需的 chart options，以及蜡烛图 candlestick options。

    参数说明：
    - `symbol`:
      - 类型：`str`
      - 用途：交易对标识（用于前端展示/缓存 key 等；不直接影响样式）。
    - `interval`:
      - 类型：`str`
      - 默认：`"1h"`
      - 用途：K 线周期标签（用于前端展示/缓存 key 等）。
    - `theme`:
      - 类型：`str`
      - 默认：`"dark"`
      - 可选：`"dark"` / `"light"`（其它值会按 light 分支处理）
      - 用途：决定背景色、网格色、上涨/下跌颜色等主题配色。

    返回值：
    - 类型：`Dict[str, Any]`
    - 字段：
      - `symbol` / `interval`
      - `chart_options`: 对应 lightweight-charts `createChart(container, options)` 的 options
      - `candlestick_options`: 对应 candlestick series 的 options（up/down 颜色等）
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
    获取某个指标（indicator_key）的默认图表映射配置。

    参数说明：
    - `indicator_key`:
      - 类型：`str`
      - 用途：指标唯一 key（例如 `"ema"`、`"rsi"`）。

    返回值：
    - 类型：`Dict[str, Any]`
    - 典型字段：
      - `display_type`: `"overlay"`（叠加到主图）或 `"pane"`（单独副图）
      - `default_color`: 默认颜色
      - `line_width` / `chart_type`: 可选配置项

    备注：
    - 未注册的指标会返回默认配置（overlay 灰色线），并打印 debug 日志。
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
    返回所有已知指标的图表映射配置。

    返回值：
    - 类型：`Dict[str, Dict[str, Any]]`
    - key 为 `indicator_key`，value 为该指标的默认映射配置 dict。
    """
    return dict(_INDICATOR_CHART_MAP)


def _to_unix_timestamp(time_value: Any) -> Optional[int]:
    """
    将多种时间表示转换为 Unix 秒级时间戳（int）。

    参数说明：
    - `time_value`:
      - 支持：`datetime`、秒/毫秒时间戳（int/str）、可被 `int(...)` 解析的值
      - 规则：如果数值大于 `1_000_000_000_000`，按毫秒处理并除以 1000

    返回值：
    - 成功：Unix 秒（int）
    - 失败：`None`
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
    将任意“类数值”转换为 float，并按指定精度四舍五入。

    参数说明：
    - `value`:
      - 支持：`str`/`int`/`float`/`Decimal` 等
      - `None` 或不可转换时返回 0.0
    - `precision`:
      - 类型：`int`
      - 默认：8
      - 用途：`round(float(value), precision)` 的小数位数

    返回值：
    - 类型：`float`
    """
    if value is None:
        return 0.0
    try:
        return round(float(value), precision)
    except (ValueError, TypeError):
        return 0.0


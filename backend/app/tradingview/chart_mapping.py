"""
TradingView图表兼容层模块。
提供与TradingView图表库兼容的数据格式转换功能。

重要说明：
    完整的TradingView Charting Library（高级图表库）需要商业授权，
    不能直接在开源项目中使用。本系统前端使用的是TradingView官方
    提供的开源替代方案 —— Lightweight Charts（轻量级图表库）。

    Lightweight Charts 项目地址：https://github.com/nickliqian/lightweight-charts
    官方文档：https://tradingview.github.io/lightweight-charts/

    本模块负责将系统内部的数据格式转换为 Lightweight Charts 所需的格式，
    同时保留与TradingView数据协议的兼容性接口，以便未来获得商业授权后
    能够无缝切换到完整版TradingView Charting Library。
"""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger


# ==================== K线数据格式转换 ====================


def klines_to_tv_format(
    klines: List[Dict[str, Any]],
    price_precision: int = 8,
) -> List[Dict[str, Any]]:
    """
    将系统内部K线数据转换为 Lightweight Charts 兼容的蜡烛图格式。

    Lightweight Charts 要求的数据格式：
    {
        "time": Unix时间戳（秒）或 "YYYY-MM-DD" 字符串,
        "open": 开盘价,
        "high": 最高价,
        "low": 最低价,
        "close": 收盘价
    }

    本函数同时保持与TradingView UDF协议的兼容性，
    在输出中额外包含 volume 字段。

    Args:
        klines: 系统K线数据列表，每项需包含 open_time, open, high, low, close, volume 字段
        price_precision: 价格小数精度，默认8位（加密货币常用精度）

    Returns:
        List[Dict[str, Any]]: Lightweight Charts 格式的K线数据列表，
            按时间升序排列
    """
    tv_klines: List[Dict[str, Any]] = []

    for kline in klines:
        # 时间戳转换：Lightweight Charts 接受 Unix秒级时间戳
        timestamp = _to_unix_timestamp(kline.get("open_time"))
        if timestamp is None:
            # 时间戳转换失败则跳过该条记录
            logger.warning(f"K线数据时间戳转换失败，跳过: {kline.get('open_time')}")
            continue

        tv_klines.append({
            "time": timestamp,
            "open": _to_float(kline.get("open"), price_precision),
            "high": _to_float(kline.get("high"), price_precision),
            "low": _to_float(kline.get("low"), price_precision),
            "close": _to_float(kline.get("close"), price_precision),
            "volume": _to_float(kline.get("volume"), 2),
        })

    # Lightweight Charts 要求数据按时间升序排列
    tv_klines.sort(key=lambda x: x["time"])

    return tv_klines


def indicator_to_tv_overlay(
    indicator_data: List[Dict[str, Any]],
    series_name: str,
    color: str = "#2196F3",
    line_width: int = 2,
) -> Dict[str, Any]:
    """
    将指标数据转换为 Lightweight Charts 叠加层（overlay）格式。

    叠加层是绘制在主图K线上方的指标线，如MA、EMA、布林带等。
    Lightweight Charts 通过 addLineSeries() 方法添加叠加层。

    Args:
        indicator_data: 指标数据列表，每项需包含 time 和 value 字段
        series_name: 系列名称，用于图例显示
        color: 线条颜色（CSS颜色值）
        line_width: 线条宽度（像素）

    Returns:
        Dict[str, Any]: Lightweight Charts 叠加层配置字典，包含：
            - name: 系列名称
            - type: 图表类型（"line"）
            - data: 数据点列表
            - options: 样式配置
    """
    formatted_data: List[Dict[str, Any]] = []

    for point in indicator_data:
        timestamp = _to_unix_timestamp(point.get("time"))
        value = point.get("value")

        if timestamp is None or value is None:
            continue

        formatted_data.append({
            "time": timestamp,
            "value": _to_float(value, 8),
        })

    # 按时间升序排列
    formatted_data.sort(key=lambda x: x["time"])

    return {
        "name": series_name,
        "type": "line",
        "data": formatted_data,
        "options": {
            "color": color,
            "lineWidth": line_width,
            "priceLineVisible": False,       # 不在价格轴显示标签
            "lastValueVisible": True,        # 显示最新值标签
            "crosshairMarkerVisible": True,  # 十字线时显示标记点
        },
    }


def indicator_to_tv_pane(
    indicator_data: List[Dict[str, Any]],
    series_name: str,
    chart_type: str = "histogram",
    color: str = "#26A69A",
) -> Dict[str, Any]:
    """
    将指标数据转换为 Lightweight Charts 独立面板（pane）格式。

    独立面板显示在主图下方，用于展示如RSI、MACD、成交量等
    不宜与价格叠加显示的指标。

    Lightweight Charts 支持的独立面板类型：
    - histogram: 柱状图（适合MACD柱、成交量等）
    - line: 折线图（适合RSI等振荡器指标）

    Args:
        indicator_data: 指标数据列表
        series_name: 系列名称
        chart_type: 图表类型，"histogram" 或 "line"
        color: 图表颜色

    Returns:
        Dict[str, Any]: Lightweight Charts 独立面板配置字典
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

        # 柱状图支持逐条设置颜色（如MACD红绿柱）
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


def markers_to_tv_format(
    signals: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    将交易信号转换为 Lightweight Charts 标记点（marker）格式。

    标记点在K线图上以箭头或圆点标注买卖信号位置，
    使用户能直观看到历史信号的触发时间和位置。

    Lightweight Charts marker 格式：
    {
        "time": Unix时间戳,
        "position": "aboveBar" 或 "belowBar",
        "color": 颜色,
        "shape": "arrowUp" 或 "arrowDown" 或 "circle",
        "text": 标签文本
    }

    Args:
        signals: 信号列表，每项需包含 time、direction（或action）和可选的 price

    Returns:
        List[Dict[str, Any]]: Lightweight Charts 标记点数据列表
    """
    markers: List[Dict[str, Any]] = []

    for signal in signals:
        timestamp = _to_unix_timestamp(signal.get("time"))
        if timestamp is None:
            continue

        direction = signal.get("direction", signal.get("action", "neutral")).lower()

        # 根据信号方向决定标记的样式
        if direction in ("long", "buy"):
            markers.append({
                "time": timestamp,
                "position": "belowBar",     # 买入标记在K线下方
                "color": "#26A69A",          # 绿色（看涨）
                "shape": "arrowUp",          # 向上箭头
                "text": signal.get("text", "买入"),
            })
        elif direction in ("short", "sell"):
            markers.append({
                "time": timestamp,
                "position": "aboveBar",     # 卖出标记在K线上方
                "color": "#EF5350",          # 红色（看跌）
                "shape": "arrowDown",        # 向下箭头
                "text": signal.get("text", "卖出"),
            })
        else:
            # 中性或平仓信号
            markers.append({
                "time": timestamp,
                "position": "aboveBar",
                "color": "#FF9800",          # 橙色（中性）
                "shape": "circle",           # 圆点
                "text": signal.get("text", "平仓"),
            })

    markers.sort(key=lambda x: x["time"])
    return markers


def build_chart_config(
    symbol: str,
    interval: str = "1h",
    theme: str = "dark",
) -> Dict[str, Any]:
    """
    构建 Lightweight Charts 的初始化配置。

    生成前端创建图表实例时所需的配置对象，
    包含图表尺寸、颜色主题、网格线、时间轴等设置。

    Args:
        symbol: 交易对名称，用于图表标题
        interval: K线时间周期
        theme: 颜色主题，"dark" 或 "light"

    Returns:
        Dict[str, Any]: Lightweight Charts createChart() 配置字典
    """
    # 深色主题配色（加密货币交易平台常用）
    dark_theme = {
        "background_color": "#1E1E2D",       # 深色背景
        "text_color": "#D1D4DC",              # 浅色文字
        "grid_color": "rgba(42, 46, 57, 0.5)", # 半透明网格线
        "border_color": "#2A2E39",            # 边框色
        "crosshair_color": "#758696",         # 十字线颜色
        "up_color": "#26A69A",                # 上涨色（绿）
        "down_color": "#EF5350",              # 下跌色（红）
    }

    # 浅色主题配色
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
                "mode": 0,  # 0=Normal模式，1=Magnet模式（自动吸附K线）
                "vertLine": {"color": colors["crosshair_color"]},
                "horzLine": {"color": colors["crosshair_color"]},
            },
            "timeScale": {
                "borderColor": colors["border_color"],
                "timeVisible": True,         # 显示时间（不仅显示日期）
                "secondsVisible": False,     # 不显示秒
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


# ==================== 指标格式映射注册表 ====================

# 系统内部指标key → Lightweight Charts 展示配置的映射
# 定义每个指标在图表上的默认展示方式
_INDICATOR_CHART_MAP: Dict[str, Dict[str, Any]] = {
    "ma": {
        "display_type": "overlay",     # 叠加在主图上
        "default_color": "#FF9800",    # 橙色
        "line_width": 1,
    },
    "ema": {
        "display_type": "overlay",
        "default_color": "#2196F3",    # 蓝色
        "line_width": 1,
    },
    "rsi": {
        "display_type": "pane",        # 独立面板
        "chart_type": "line",
        "default_color": "#AB47BC",    # 紫色
    },
    "macd": {
        "display_type": "pane",
        "chart_type": "histogram",
        "default_color": "#26A69A",    # 绿色
    },
    "vwap": {
        "display_type": "overlay",
        "default_color": "#FFC107",    # 黄色
        "line_width": 2,
    },
    "volume_spike": {
        "display_type": "pane",
        "chart_type": "histogram",
        "default_color": "#42A5F5",    # 浅蓝
    },
}


def get_indicator_chart_config(indicator_key: str) -> Dict[str, Any]:
    """
    获取指定指标的图表展示配置。

    如果指标已在映射表中注册，返回预定义配置；
    否则返回默认的叠加层配置。

    Args:
        indicator_key: 指标唯一标识

    Returns:
        Dict[str, Any]: 指标的图表展示配置
    """
    if indicator_key in _INDICATOR_CHART_MAP:
        return _INDICATOR_CHART_MAP[indicator_key]

    # 未注册的指标使用默认的叠加层配置
    logger.debug(f"指标 '{indicator_key}' 未在图表映射中注册，使用默认配置")
    return {
        "display_type": "overlay",
        "default_color": "#9E9E9E",  # 灰色（表示未特别配置）
        "line_width": 1,
    }


def get_available_chart_indicators() -> Dict[str, Dict[str, Any]]:
    """
    获取所有已注册的图表指标映射表。

    供前端配置页面使用，让用户知道哪些指标支持图表展示
    以及它们的默认展示方式。

    Returns:
        Dict[str, Dict[str, Any]]: 指标key到图表配置的完整映射
    """
    return dict(_INDICATOR_CHART_MAP)


# ==================== 内部工具函数 ====================


def _to_unix_timestamp(time_value: Any) -> Optional[int]:
    """
    将各种时间格式统一转换为Unix秒级时间戳。

    支持的输入格式：
    - datetime对象
    - 整数/浮点数（毫秒级时间戳，自动转为秒级）
    - 已经是秒级的整数

    Args:
        time_value: 需要转换的时间值

    Returns:
        Optional[int]: Unix秒级时间戳，转换失败返回None
    """
    if time_value is None:
        return None

    # datetime对象 → Unix时间戳
    if isinstance(time_value, datetime):
        return int(time_value.timestamp())

    # 数值类型：判断是毫秒还是秒
    try:
        numeric_val = int(time_value)
        # 大于1e12的数值判定为毫秒级时间戳（2001年之后的毫秒值）
        if numeric_val > 1_000_000_000_000:
            return numeric_val // 1000  # 毫秒转秒
        return numeric_val
    except (ValueError, TypeError):
        return None


def _to_float(value: Any, precision: int = 8) -> float:
    """
    将值安全转换为指定精度的浮点数。

    处理Decimal、字符串、整数等各种输入类型。

    Args:
        value: 需要转换的值
        precision: 小数精度位数

    Returns:
        float: 转换后的浮点数，失败返回0.0
    """
    if value is None:
        return 0.0
    try:
        return round(float(value), precision)
    except (ValueError, TypeError):
        return 0.0

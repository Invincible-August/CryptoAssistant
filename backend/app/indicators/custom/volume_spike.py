"""
成交量异动（Volume Spike）指标模块。
检测成交量是否相对于历史均值出现异常放大，辅助判断市场异动。
"""
from typing import Any, Dict, List

import pandas as pd

from app.indicators.base import BaseIndicator


class VolumeSpikeIndicator(BaseIndicator):
    """
    成交量异动检测指标（Volume Spike）。

    通过将当前K线的成交量与过去N根K线的平均成交量进行对比，
    计算成交量比率（volume_ratio），当比率超过设定阈值时判定为"异动"。

    应用场景：
    - 放量突破：价格突破关键位时伴随成交量异动，突破有效性更高
    - 异常交易：突然的大幅放量可能暗示主力资金进出或重大消息
    - 趋势确认：趋势行情中放量方向与趋势一致可增强信心

    计算公式：
        volume_avg = SMA(volume, window)
        volume_ratio = current_volume / volume_avg
        is_spike = volume_ratio >= spike_threshold
    """

    # ========== 指标身份标识 ==========
    indicator_key: str = "volume_spike"
    name: str = "成交量异动检测"
    description: str = "检测成交量相对历史均值的异常放大，辅助判断市场异动信号"
    source: str = "human"  # 人工自定义指标
    version: str = "1.0.0"
    category: str = "volume"

    # ========== 兼容性声明 ==========
    input_type: List[str] = ["kline"]
    chart_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ========== 参数定义 ==========
    params_schema: Dict[str, Any] = {
        "window": {
            "type": "int",
            "required": False,
            "default": 20,
            "description": "计算成交量均值的滚动窗口大小（K线根数）",
        },
        "spike_threshold": {
            "type": "float",
            "required": False,
            "default": 2.0,
            "description": "异动判定阈值，当 volume_ratio >= 该值时视为异动（默认2.0即2倍）",
        },
    }

    # ========== 输出定义 ==========
    output_schema: Dict[str, Any] = {
        "open_time": {
            "type": "datetime",
            "description": "K线开盘时间",
        },
        "volume_avg": {
            "type": "float",
            "description": "过去N根K线的平均成交量",
        },
        "volume_ratio": {
            "type": "float",
            "description": "当前成交量与平均成交量的比率",
        },
        "is_spike": {
            "type": "bool",
            "description": "是否触发异动（True/False）",
        },
    }

    # ========== 前端图表展示配置 ==========
    display_config: Dict[str, Any] = {
        "panel": "sub",  # 在副图独立面板显示
        "series": [
            {
                "field": "volume_ratio",
                "type": "histogram",
                "color": "#7C4DFF",
                "name": "成交量比率",
            },
            {
                "field": "volume_avg",
                "type": "line",
                "color": "#FF9800",
                "name": "成交量均值",
            },
        ],
        # 异动阈值参考线
        "reference_lines": [
            {
                "value": 2.0,
                "color": "#F44336",
                "label": "异动阈值",
                "style": "dashed",
            },
            {
                "value": 1.0,
                "color": "#9E9E9E",
                "label": "基准线",
                "style": "dotted",
            },
        ],
        # 异动标记：在图表上用特殊标记高亮异动点
        "markers": {
            "field": "is_spike",
            "condition": True,
            "shape": "triangle_up",
            "color": "#F44336",
            "label": "放量异动",
        },
    }

    @classmethod
    def calculate(cls, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        计算成交量异动指标。

        Args:
            df: K线数据DataFrame，必须包含 open_time 和 volume 列。
            params: 参数字典，支持 window（窗口大小）和 spike_threshold（异动阈值）。

        Returns:
            pd.DataFrame: 包含 open_time, volume_avg, volume_ratio, is_spike 列的结果。
        """
        # 校验并补全参数
        validated_params: Dict[str, Any] = cls.validate_params(params)
        window: int = validated_params["window"]
        spike_threshold: float = validated_params["spike_threshold"]

        # 第1步：计算滚动窗口内的平均成交量
        # min_periods=window 确保窗口内数据不足时输出NaN
        volume_avg: pd.Series = df["volume"].rolling(
            window=window, min_periods=window
        ).mean()

        # 第2步：计算成交量比率 = 当前成交量 / 平均成交量
        # 比率 > 1 表示当前成交量高于历史均值
        # 比率 < 1 表示当前成交量低于历史均值
        volume_ratio: pd.Series = df["volume"] / volume_avg

        # 第3步：判断是否触发异动
        # 比率 >= 阈值（默认2.0倍）时标记为异动
        is_spike: pd.Series = volume_ratio >= spike_threshold

        # 组装输出DataFrame
        result_df: pd.DataFrame = pd.DataFrame({
            "open_time": df["open_time"],
            "volume_avg": volume_avg,
            "volume_ratio": volume_ratio,
            "is_spike": is_spike,
        })

        return result_df

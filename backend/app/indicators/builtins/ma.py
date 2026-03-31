"""
简单移动平均线（SMA）指标模块。
计算指定周期内收盘价的算术平均值，是最基础的趋势跟踪指标。
"""
from typing import Any, Dict, List

import pandas as pd

from app.indicators.base import BaseIndicator


class SMAIndicator(BaseIndicator):
    """
    简单移动平均线（Simple Moving Average）指标。

    SMA 通过对指定周期内的收盘价取算术平均值来平滑价格波动，
    帮助交易者识别价格趋势方向和支撑/阻力位。

    计算公式：
        SMA(n) = (C1 + C2 + ... + Cn) / n
        其中 C 为收盘价，n 为周期长度。
    """

    # ========== 指标身份标识 ==========
    indicator_key: str = "ma"
    name: str = "简单移动平均线"
    description: str = "计算指定周期的收盘价简单移动平均值，用于判断趋势方向"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "trend"

    # ========== 兼容性声明 ==========
    input_type: List[str] = ["kline"]
    chart_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ========== 参数定义 ==========
    params_schema: Dict[str, Any] = {
        "period": {
            "type": "int",
            "required": False,
            "default": 20,
            "description": "移动平均周期长度，常用值：5/10/20/60/120",
        }
    }

    # ========== 输出定义 ==========
    output_schema: Dict[str, Any] = {
        "open_time": {
            "type": "datetime",
            "description": "K线开盘时间",
        },
        "ma_{period}": {
            "type": "float",
            "description": "SMA计算结果，列名中{period}会被实际周期值替换",
        },
    }

    # ========== 前端图表展示配置 ==========
    display_config: Dict[str, Any] = {
        "panel": "main",  # 在主图上叠加显示
        "series": [
            {
                "field": "ma_{period}",
                "type": "line",
                "color": "#FF9800",
                "name": "MA({period})",
            }
        ],
    }

    @classmethod
    def calculate(cls, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        计算简单移动平均线。

        Args:
            df: K线数据DataFrame，必须包含 open_time 和 close 列。
            params: 参数字典，支持 period（周期长度）。

        Returns:
            pd.DataFrame: 包含 open_time 和 ma_{period} 列的结果DataFrame。
        """
        # 校验并补全参数
        validated_params: Dict[str, Any] = cls.validate_params(params)
        period: int = validated_params["period"]

        # 使用 pandas rolling 窗口计算算术平均值
        # min_periods=period 确保窗口内数据量不足时输出NaN
        column_name: str = f"ma_{period}"
        sma_series: pd.Series = df["close"].rolling(
            window=period, min_periods=period
        ).mean()

        # 组装输出DataFrame，只保留schema定义的列
        result_df: pd.DataFrame = pd.DataFrame({
            "open_time": df["open_time"],
            column_name: sma_series,
        })

        return result_df


# ---- Compatibility alias ----
# Some test/code paths import `MAIndicator` instead of `SMAIndicator`.
# Keep it as an alias so registration and runtime behavior remain unchanged.
MAIndicator = SMAIndicator

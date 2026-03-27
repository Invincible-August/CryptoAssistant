"""
成交量加权平均价（VWAP）指标模块。
综合考虑价格和成交量，反映市场真实的平均成交成本。
"""
from typing import Any, Dict, List

import pandas as pd

from app.indicators.base import BaseIndicator


class VWAPIndicator(BaseIndicator):
    """
    成交量加权平均价（Volume Weighted Average Price）指标。

    VWAP 将每根K线的典型价格（Typical Price）乘以成交量后累加，
    再除以累计成交量，反映一段时间内市场的真实平均成交价格。

    用途：
    - 机构交易者用VWAP评估执行质量（成交价优于VWAP则为好的执行）
    - 价格在VWAP上方表示多方控制，下方表示空方控制
    - VWAP常作为日内交易的动态支撑/阻力位

    计算公式（滚动窗口版本）：
        典型价格 TP = (High + Low + Close) / 3
        VWAP(n) = Σ(TP × Volume, n) / Σ(Volume, n)
        其中 n 为滚动窗口周期。
    """

    # ========== 指标身份标识 ==========
    indicator_key: str = "vwap"
    name: str = "成交量加权平均价"
    description: str = "综合价格和成交量的加权平均价格，反映市场真实成交成本"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "volume"

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
            "description": "VWAP滚动窗口周期，默认20根K线",
        }
    }

    # ========== 输出定义 ==========
    output_schema: Dict[str, Any] = {
        "open_time": {
            "type": "datetime",
            "description": "K线开盘时间",
        },
        "vwap": {
            "type": "float",
            "description": "成交量加权平均价",
        },
    }

    # ========== 前端图表展示配置 ==========
    display_config: Dict[str, Any] = {
        "panel": "main",  # VWAP在主图上叠加显示
        "series": [
            {
                "field": "vwap",
                "type": "line",
                "color": "#E91E63",
                "name": "VWAP({period})",
            }
        ],
    }

    @classmethod
    def calculate(cls, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        计算滚动窗口VWAP。

        Args:
            df: K线数据DataFrame，必须包含 open_time, high, low, close, volume 列。
            params: 参数字典，支持 period（滚动窗口周期）。

        Returns:
            pd.DataFrame: 包含 open_time 和 vwap 列的结果DataFrame。
        """
        # 校验并补全参数
        validated_params: Dict[str, Any] = cls.validate_params(params)
        period: int = validated_params["period"]

        # 第1步：计算典型价格 TP = (最高价 + 最低价 + 收盘价) / 3
        # 典型价格比单纯使用收盘价更能代表每根K线的真实价格水平
        typical_price: pd.Series = (df["high"] + df["low"] + df["close"]) / 3

        # 第2步：计算 TP × Volume（价量乘积）
        # 这是VWAP分子的基础数据
        tp_volume_product: pd.Series = typical_price * df["volume"]

        # 第3步：在滚动窗口内分别求和 TP×Volume 和 Volume
        rolling_tp_volume_sum: pd.Series = tp_volume_product.rolling(
            window=period, min_periods=period
        ).sum()
        rolling_volume_sum: pd.Series = df["volume"].rolling(
            window=period, min_periods=period
        ).sum()

        # 第4步：VWAP = 累计价量乘积 / 累计成交量
        # 当成交量为0时会产生NaN，这是预期行为（无成交时VWAP无意义）
        vwap_series: pd.Series = rolling_tp_volume_sum / rolling_volume_sum

        # 组装输出DataFrame
        result_df: pd.DataFrame = pd.DataFrame({
            "open_time": df["open_time"],
            "vwap": vwap_series,
        })

        return result_df

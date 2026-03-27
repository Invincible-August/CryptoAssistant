"""
MACD（Moving Average Convergence Divergence）指标模块。
通过快慢两条EMA的差离值来捕捉趋势变化和动量强弱。
"""
from typing import Any, Dict, List

import pandas as pd

from app.indicators.base import BaseIndicator


class MACDIndicator(BaseIndicator):
    """
    MACD 指标（Moving Average Convergence Divergence）。

    MACD 由三个部分组成：
    - DIF（差离值）：快速EMA与慢速EMA的差值，反映短期与中期趋势的偏离程度
    - DEA（信号线）：DIF的EMA平滑值，用于产生交叉信号
    - MACD柱（柱状图）：DIF与DEA的差值 × 2，直观显示多空力量对比

    经典交易信号：
    - 金叉（DIF上穿DEA）→ 看多
    - 死叉（DIF下穿DEA）→ 看空
    - 柱状图由负转正 → 多方力量增强
    - 背离（价格创新高/低但MACD未同步）→ 趋势反转预警

    计算公式：
        DIF = EMA(close, fast_period) - EMA(close, slow_period)
        DEA = EMA(DIF, signal_period)
        MACD柱 = (DIF - DEA) × 2
    """

    # ========== 指标身份标识 ==========
    indicator_key: str = "macd"
    name: str = "MACD指标"
    description: str = "由DIF/DEA/柱状图组成的趋势动量指标，用于判断趋势方向和强弱变化"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "momentum"

    # ========== 兼容性声明 ==========
    input_type: List[str] = ["kline"]
    chart_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ========== 参数定义 ==========
    params_schema: Dict[str, Any] = {
        "fast_period": {
            "type": "int",
            "required": False,
            "default": 12,
            "description": "快速EMA周期，经典值12",
        },
        "slow_period": {
            "type": "int",
            "required": False,
            "default": 26,
            "description": "慢速EMA周期，经典值26",
        },
        "signal_period": {
            "type": "int",
            "required": False,
            "default": 9,
            "description": "信号线EMA周期，经典值9",
        },
    }

    # ========== 输出定义 ==========
    output_schema: Dict[str, Any] = {
        "open_time": {
            "type": "datetime",
            "description": "K线开盘时间",
        },
        "dif": {
            "type": "float",
            "description": "DIF值（快线-慢线），又称MACD线",
        },
        "dea": {
            "type": "float",
            "description": "DEA值（DIF的EMA），又称信号线",
        },
        "macd_hist": {
            "type": "float",
            "description": "MACD柱状图值 = (DIF - DEA) × 2",
        },
    }

    # ========== 前端图表展示配置 ==========
    display_config: Dict[str, Any] = {
        "panel": "sub",  # MACD在副图独立面板显示
        "series": [
            {
                "field": "dif",
                "type": "line",
                "color": "#2196F3",
                "name": "DIF",
            },
            {
                "field": "dea",
                "type": "line",
                "color": "#FF9800",
                "name": "DEA",
            },
            {
                "field": "macd_hist",
                "type": "histogram",
                "color_positive": "#F44336",  # 红色柱体（多方）
                "color_negative": "#4CAF50",  # 绿色柱体（空方）
                "name": "MACD柱",
            },
        ],
        # 零轴参考线
        "reference_lines": [
            {"value": 0, "color": "#9E9E9E", "label": "零轴", "style": "solid"},
        ],
    }

    @classmethod
    def calculate(cls, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        计算MACD指标（DIF、DEA、MACD柱状图）。

        Args:
            df: K线数据DataFrame，必须包含 open_time 和 close 列。
            params: 参数字典，支持 fast_period / slow_period / signal_period。

        Returns:
            pd.DataFrame: 包含 open_time, dif, dea, macd_hist 列的结果DataFrame。
        """
        # 校验并补全参数
        validated_params: Dict[str, Any] = cls.validate_params(params)
        fast_period: int = validated_params["fast_period"]
        slow_period: int = validated_params["slow_period"]
        signal_period: int = validated_params["signal_period"]

        close_prices: pd.Series = df["close"]

        # 第1步：计算快速EMA（短周期，对价格变化更敏感）
        ema_fast: pd.Series = close_prices.ewm(
            span=fast_period, adjust=False
        ).mean()

        # 第2步：计算慢速EMA（长周期，反映中期趋势）
        ema_slow: pd.Series = close_prices.ewm(
            span=slow_period, adjust=False
        ).mean()

        # 第3步：DIF = 快速EMA - 慢速EMA
        # DIF > 0 表示短期趋势强于中期趋势（多方占优）
        dif: pd.Series = ema_fast - ema_slow

        # 第4步：DEA = DIF的EMA平滑（信号线）
        # DEA滞后于DIF，两线交叉产生买卖信号
        dea: pd.Series = dif.ewm(span=signal_period, adjust=False).mean()

        # 第5步：MACD柱 = (DIF - DEA) × 2
        # 乘以2是为了放大差值，使柱状图更直观
        macd_hist: pd.Series = (dif - dea) * 2

        # 组装输出DataFrame
        result_df: pd.DataFrame = pd.DataFrame({
            "open_time": df["open_time"],
            "dif": dif,
            "dea": dea,
            "macd_hist": macd_hist,
        })

        return result_df

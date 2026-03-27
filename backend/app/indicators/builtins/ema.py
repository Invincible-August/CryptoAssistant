"""
指数移动平均线（EMA）指标模块。
对近期价格赋予更高权重，相比SMA对价格变化更敏感。
"""
from typing import Any, Dict, List

import pandas as pd

from app.indicators.base import BaseIndicator


class EMAIndicator(BaseIndicator):
    """
    指数移动平均线（Exponential Moving Average）指标。

    EMA 通过指数加权方式计算移动平均值，赋予近期价格更大的权重，
    因此比SMA更快反映价格的最新变化，适用于短线趋势判断。

    计算公式：
        平滑因子 α = 2 / (n + 1)
        EMA(t) = α × Close(t) + (1 - α) × EMA(t-1)
        其中 n 为周期长度。
    """

    # ========== 指标身份标识 ==========
    indicator_key: str = "ema"
    name: str = "指数移动平均线"
    description: str = "指数加权移动平均线，对近期价格赋予更高权重，趋势响应更灵敏"
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
            "description": "EMA周期长度，常用值：12/20/26/50/200",
        }
    }

    # ========== 输出定义 ==========
    output_schema: Dict[str, Any] = {
        "open_time": {
            "type": "datetime",
            "description": "K线开盘时间",
        },
        "ema_{period}": {
            "type": "float",
            "description": "EMA计算结果，列名中{period}会被实际周期值替换",
        },
    }

    # ========== 前端图表展示配置 ==========
    display_config: Dict[str, Any] = {
        "panel": "main",  # 在主图上叠加显示
        "series": [
            {
                "field": "ema_{period}",
                "type": "line",
                "color": "#2196F3",
                "name": "EMA({period})",
            }
        ],
    }

    @classmethod
    def calculate(cls, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        计算指数移动平均线。

        使用 pandas ewm (Exponentially Weighted Moving) 方法，
        span 参数对应EMA周期，pandas内部自动计算平滑因子 α = 2/(span+1)。

        Args:
            df: K线数据DataFrame，必须包含 open_time 和 close 列。
            params: 参数字典，支持 period（周期长度）。

        Returns:
            pd.DataFrame: 包含 open_time 和 ema_{period} 列的结果DataFrame。
        """
        # 校验并补全参数
        validated_params: Dict[str, Any] = cls.validate_params(params)
        period: int = validated_params["period"]

        # 使用 pandas ewm 计算指数移动平均
        # span=period 对应周期长度，adjust=False 使用递归计算方式（更贴近传统EMA定义）
        column_name: str = f"ema_{period}"
        ema_series: pd.Series = df["close"].ewm(
            span=period, adjust=False
        ).mean()

        # 组装输出DataFrame
        result_df: pd.DataFrame = pd.DataFrame({
            "open_time": df["open_time"],
            column_name: ema_series,
        })

        return result_df

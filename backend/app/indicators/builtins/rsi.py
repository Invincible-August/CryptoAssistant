"""
相对强弱指标（RSI）模块。
通过衡量价格涨跌幅度的比率来判断市场超买/超卖状态。
"""
from typing import Any, Dict, List

import pandas as pd

from app.indicators.base import BaseIndicator


class RSIIndicator(BaseIndicator):
    """
    相对强弱指标（Relative Strength Index）。

    RSI 是一种动量振荡器，通过比较一段时间内收盘价上涨和下跌的幅度，
    来评估价格变动的速度和强度。取值范围 0~100：
    - RSI > 70 通常被视为超买区域（可能回调）
    - RSI < 30 通常被视为超卖区域（可能反弹）

    计算步骤（Wilder平滑法）：
    1. 计算每根K线相对于前一根的价格变动 delta
    2. 分离涨幅（gains）和跌幅（losses）
    3. 用指数移动平均分别平滑 gains 和 losses
    4. RS = avg_gain / avg_loss
    5. RSI = 100 - 100 / (1 + RS)
    """

    # ========== 指标身份标识 ==========
    indicator_key: str = "rsi"
    name: str = "相对强弱指标"
    description: str = "衡量价格涨跌力度的动量指标，用于判断超买超卖状态"
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
        "period": {
            "type": "int",
            "required": False,
            "default": 14,
            "description": "RSI计算周期，经典值为14",
        }
    }

    # ========== 输出定义 ==========
    output_schema: Dict[str, Any] = {
        "open_time": {
            "type": "datetime",
            "description": "K线开盘时间",
        },
        "rsi": {
            "type": "float",
            "description": "RSI值，范围0~100",
        },
    }

    # ========== 前端图表展示配置 ==========
    display_config: Dict[str, Any] = {
        "panel": "sub",  # RSI在副图独立面板显示
        "series": [
            {
                "field": "rsi",
                "type": "line",
                "color": "#9C27B0",
                "name": "RSI({period})",
            }
        ],
        # 超买超卖参考线
        "reference_lines": [
            {"value": 70, "color": "#F44336", "label": "超买线", "style": "dashed"},
            {"value": 30, "color": "#4CAF50", "label": "超卖线", "style": "dashed"},
            {"value": 50, "color": "#9E9E9E", "label": "中轴线", "style": "dotted"},
        ],
        "y_range": [0, 100],
    }

    @classmethod
    def calculate(cls, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        计算RSI指标（Wilder平滑法）。

        Args:
            df: K线数据DataFrame，必须包含 open_time 和 close 列。
            params: 参数字典，支持 period（RSI周期）。

        Returns:
            pd.DataFrame: 包含 open_time 和 rsi 列的结果DataFrame。
        """
        # 校验并补全参数
        validated_params: Dict[str, Any] = cls.validate_params(params)
        period: int = validated_params["period"]

        # 第1步：计算相邻K线的收盘价差值
        delta: pd.Series = df["close"].diff()

        # 第2步：分离涨幅和跌幅
        # 涨幅：delta > 0 的部分取原值，其余置零
        gains: pd.Series = delta.clip(lower=0)
        # 跌幅：delta < 0 的部分取绝对值，其余置零
        losses: pd.Series = (-delta).clip(lower=0)

        # 第3步：使用 Wilder 平滑法（等价于 alpha=1/period 的指数移动平均）
        # com = period - 1 对应 alpha = 1/period（Wilder原始定义）
        avg_gain: pd.Series = gains.ewm(com=period - 1, min_periods=period).mean()
        avg_loss: pd.Series = losses.ewm(com=period - 1, min_periods=period).mean()

        # 第4步：计算相对强度 RS = 平均涨幅 / 平均跌幅
        rs: pd.Series = avg_gain / avg_loss

        # 第5步：将RS转换为RSI（0~100范围）
        # 当 avg_loss 为0时 rs 为 inf，此时 RSI = 100（极端超买）
        rsi_series: pd.Series = 100 - (100 / (1 + rs))

        # 组装输出DataFrame
        result_df: pd.DataFrame = pd.DataFrame({
            "open_time": df["open_time"],
            "rsi": rsi_series,
        })

        return result_df

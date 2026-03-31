"""
持仓量变化因子模块。
基于OI（Open Interest）数据和K线数据，
计算持仓量变化率及其与价格的相关性，用于判断市场持仓行为。
"""
import math
from typing import Any, Dict, List

from loguru import logger

from app.factors.base import BaseFactor


class OIChangeFactor(BaseFactor):
    """
    持仓量变化因子。

    分析合约市场的未平仓量（OI）变化趋势：
    - OI上升 + 价格上升 → 多头主动开仓，趋势可能延续
    - OI上升 + 价格下跌 → 空头主动开仓，做空力量增强
    - OI下降 + 价格上升 → 空头平仓（空头回补），可能是反弹
    - OI下降 + 价格下跌 → 多头平仓（多头止损），下跌动能减弱

    注意：OI数据仅在合约交易对中可用，现货交易对无此数据。
    """

    factor_key: str = "oi_change"
    name: str = "持仓量变化因子"
    description: str = "分析OI变化率及价格-OI相关性，推断市场持仓行为和力量对比"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "positioning"
    input_type: List[str] = ["open_interest", "kline"]
    score_weight: float = 0.9
    signal_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ==================== 参数定义 ====================
    params_schema: Dict[str, Any] = {
        "period": {
            "type": "int",
            "default": 14,
            "required": False,
            "description": "OI变化率和相关性的计算周期",
            "min": 3,
            "max": 100,
        },
    }

    # ==================== 输出字段定义 ====================
    output_schema: Dict[str, Any] = {
        "oi_change_rate": {
            "type": "float",
            "description": "OI变化率（百分比），正值表示持仓增加",
        },
        "oi_price_correlation": {
            "type": "float",
            "description": "OI变化与价格变化的皮尔逊相关系数（-1到1）",
        },
        "oi_score": {
            "type": "float",
            "description": "OI综合评分（0-100），结合变化率和相关性",
        },
    }

    # ==================== 前端展示配置 ====================
    display_config: Dict[str, Any] = {
        "chart_type": "line",
        "primary_field": "oi_score",
        "secondary_field": "oi_change_rate",
        "overlay": False,
        "color": "#8E44AD",
        "y_axis_label": "OI评分",
    }

    @classmethod
    def calculate(cls, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算持仓量变化因子。

        Args:
            context: 数据上下文，需包含：
                     - "open_interest": OI数据列表，每项包含 "oi" 字段
                     - "kline": K线数据列表，每项包含 "close" 字段
            params:  参数字典，支持 period。

        Returns:
            Dict[str, Any]: 包含 oi_change_rate、oi_price_correlation、oi_score
        """
        # ---------- 参数校验 ----------
        validated_params = cls.validate_params(params)
        period: int = validated_params["period"]

        # ---------- 获取数据 ----------
        oi_data: List[Dict[str, Any]] = context.get("open_interest", [])
        kline_data: List[Dict[str, Any]] = context.get("kline", [])

        # 兼容：某些路径传入的是 dict / pandas.DataFrame
        try:
            import pandas as pd  # type: ignore

            if isinstance(kline_data, pd.DataFrame):
                kline_data = kline_data.to_dict("records")  # type: ignore[assignment]
        except Exception:  # noqa: BLE001
            pass

        if isinstance(oi_data, dict):
            # 期望结构：[{ "oi": <value>, ... }]
            oi_value = oi_data.get("open_interest", 0.0)
            oi_data = [{"oi": oi_value, "event_time": oi_data.get("event_time")}]

        # 优雅降级：OI数据不可用时返回中性结果
        if not oi_data or len(oi_data) < period + 1:
            logger.debug(
                f"OI变化因子: OI数据不足（需要 {period + 1} 条，"
                f"实际 {len(oi_data)} 条），返回中性默认值"
            )
            return cls._default_result()

        # ---------- 提取OI序列 ----------
        oi_values: List[float] = [float(item["oi"]) for item in oi_data]

        # ---------- 1. 计算OI变化率 ----------
        current_oi = oi_values[-1]
        past_oi = oi_values[-(period + 1)]
        oi_change_rate: float = 0.0
        if past_oi > 0:
            oi_change_rate = ((current_oi - past_oi) / past_oi) * 100

        # ---------- 2. 计算OI与价格的皮尔逊相关系数 ----------
        oi_price_correlation = cls._calculate_correlation(
            oi_data=oi_values,
            kline_data=kline_data,
            period=period,
        )

        # ---------- 3. 综合评分 ----------
        oi_score = cls._compute_oi_score(
            oi_change_rate=oi_change_rate,
            oi_price_correlation=oi_price_correlation,
        )

        return {
            "oi_change_rate": round(oi_change_rate, 4),
            "oi_price_correlation": round(oi_price_correlation, 4),
            "oi_score": round(oi_score, 2),
        }

    @classmethod
    def _calculate_correlation(
        cls,
        oi_data: List[float],
        kline_data: List[Dict[str, Any]],
        period: int,
    ) -> float:
        """
        计算OI变化与价格变化的皮尔逊相关系数。

        皮尔逊相关系数公式：
        r = Σ((x_i - x̄)(y_i - ȳ)) / √(Σ(x_i - x̄)² * Σ(y_i - ȳ)²)

        这里 x = OI变化序列，y = 价格变化序列。

        Args:
            oi_data:    OI数值序列
            kline_data: K线数据列表
            period:     计算周期

        Returns:
            float: 相关系数（-1到1），数据不足时返回0
        """
        # K线数据不足时无法计算相关性
        if len(kline_data) < period + 1:
            return 0.0

        close_prices: List[float] = [
            float(candle["close"]) for candle in kline_data
        ]

        # 取最近 period+1 个数据点来计算 period 个变化量
        recent_oi = oi_data[-(period + 1):]
        recent_prices = close_prices[-(period + 1):]

        # 计算逐期变化量
        oi_changes: List[float] = [
            recent_oi[i] - recent_oi[i - 1]
            for i in range(1, len(recent_oi))
        ]
        price_changes: List[float] = [
            recent_prices[i] - recent_prices[i - 1]
            for i in range(1, len(recent_prices))
        ]

        # 确保两个序列等长
        min_len = min(len(oi_changes), len(price_changes))
        if min_len < 3:
            return 0.0

        oi_changes = oi_changes[:min_len]
        price_changes = price_changes[:min_len]

        # 计算均值
        oi_mean = sum(oi_changes) / min_len
        price_mean = sum(price_changes) / min_len

        # 计算皮尔逊相关系数的分子和分母
        numerator: float = 0.0
        oi_var: float = 0.0
        price_var: float = 0.0

        for i in range(min_len):
            oi_diff = oi_changes[i] - oi_mean
            price_diff = price_changes[i] - price_mean
            numerator += oi_diff * price_diff
            oi_var += oi_diff ** 2
            price_var += price_diff ** 2

        denominator = math.sqrt(oi_var * price_var)

        # 分母为0说明某一序列无变化，返回0
        if denominator == 0:
            return 0.0

        correlation = numerator / denominator
        # 限制到 [-1, 1] 范围（防止浮点误差）
        return max(-1.0, min(1.0, correlation))

    @classmethod
    def _compute_oi_score(
        cls,
        oi_change_rate: float,
        oi_price_correlation: float,
    ) -> float:
        """
        综合OI变化率和相关性计算评分。

        评分逻辑（反映多头主导程度）：
        - OI增加 + 正相关（多头开仓）→ 高分
        - OI减少 + 负相关（空头平仓/多头止损）→ 低分
        - OI变化率通过 sigmoid 映射到 0-100
        - 相关性作为方向调节因子

        Args:
            oi_change_rate:      OI变化率（百分比）
            oi_price_correlation: OI与价格的相关系数

        Returns:
            float: OI综合评分（0-100）
        """
        # OI变化率分量：通过 sigmoid 映射
        # 变化率通常在 -20%~+20% 之间，中心设为 0
        sigmoid_k = 0.2
        change_score = 100.0 / (1.0 + math.exp(-sigmoid_k * oi_change_rate))

        # 相关性调节分量：
        # 正相关时（OI和价格同向）增强多头信号
        # 负相关时减弱多头信号
        # 映射：相关系数 -1~1 → 0~100
        correlation_score = (oi_price_correlation + 1.0) / 2.0 * 100.0

        # 加权合成（变化率 60%，相关性 40%）
        final_score = change_score * 0.60 + correlation_score * 0.40

        return max(0.0, min(100.0, final_score))

    @classmethod
    def _default_result(cls) -> Dict[str, Any]:
        """
        返回中性默认结果。
        在OI数据不可用时使用，保证下游模块不会因缺失数据而异常。

        Returns:
            Dict[str, Any]: 所有字段为中性值的结果字典
        """
        return {
            "oi_change_rate": 0.0,
            "oi_price_correlation": 0.0,
            "oi_score": 50.0,
        }

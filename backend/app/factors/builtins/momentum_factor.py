"""
动量因子模块。
基于K线数据计算价格变化率(ROC)、加速度和趋势一致性，
综合输出动量评分，用于捕捉价格运动的强度和持续性。
"""
import math
from typing import Any, Dict, List

from app.factors.base import BaseFactor


class MomentumFactor(BaseFactor):
    """
    动量因子。

    计算逻辑：
    1. ROC（Rate of Change）：当前价格相对于 N 周期前的变化率
    2. 加速度（Acceleration）：ROC 的变化率，衡量动量的加速/减速
    3. 趋势一致性（Trend Consistency）：N 周期内价格连续同向变动的比例
    4. 综合评分：加权合成以上三个维度，映射到 0-100 区间
    """

    factor_key: str = "momentum"
    name: str = "动量因子"
    description: str = "计算价格变化率、加速度和趋势一致性，综合评估动量强度"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "momentum"
    input_type: List[str] = ["kline"]
    score_weight: float = 1.0
    signal_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ==================== 参数定义 ====================
    params_schema: Dict[str, Any] = {
        "period": {
            "type": "int",
            "default": 14,
            "required": False,
            "description": "ROC计算周期，即回看K线根数",
            "min": 2,
            "max": 200,
        },
        "acceleration_period": {
            "type": "int",
            "default": 5,
            "required": False,
            "description": "加速度计算周期，用于衡量ROC变化速率",
            "min": 2,
            "max": 50,
        },
    }

    # ==================== 输出字段定义 ====================
    output_schema: Dict[str, Any] = {
        "roc": {
            "type": "float",
            "description": "价格变化率（百分比），正值表示上涨动量",
        },
        "acceleration": {
            "type": "float",
            "description": "动量加速度，正值表示动量增强",
        },
        "trend_consistency": {
            "type": "float",
            "description": "趋势一致性比率（0-1），越高表示趋势越连贯",
        },
        "momentum_score": {
            "type": "float",
            "description": "综合动量评分（0-100），50为中性",
        },
    }

    # ==================== 前端展示配置 ====================
    display_config: Dict[str, Any] = {
        "chart_type": "line",
        "primary_field": "momentum_score",
        "overlay": False,
        "color": "#FF6B35",
        "y_axis_label": "动量评分",
    }

    @classmethod
    def calculate(cls, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算动量因子。

        Args:
            context: 数据上下文，需包含 "kline" 键，其值为K线数据列表。
                     每根K线至少包含 "close" 字段。
            params:  参数字典，支持 period 和 acceleration_period。

        Returns:
            Dict[str, Any]: 包含 roc、acceleration、trend_consistency、momentum_score 的结果
        """
        # ---------- 参数校验与提取 ----------
        validated_params = cls.validate_params(params)
        period: int = validated_params["period"]
        acceleration_period: int = validated_params["acceleration_period"]

        # ---------- 获取K线数据 ----------
        kline_data: List[Dict[str, Any]] = context.get("kline", [])

        # 数据量不足时返回中性默认值
        if len(kline_data) < period + acceleration_period:
            return {
                "roc": 0.0,
                "acceleration": 0.0,
                "trend_consistency": 0.0,
                "momentum_score": 50.0,
            }

        # 提取收盘价序列
        close_prices: List[float] = [
            float(candle["close"]) for candle in kline_data
        ]

        # ---------- 1. 计算 ROC（价格变化率） ----------
        # ROC = (当前价 - N周期前价格) / N周期前价格 * 100
        current_price = close_prices[-1]
        past_price = close_prices[-(period + 1)]
        roc: float = ((current_price - past_price) / past_price * 100) if past_price != 0 else 0.0

        # ---------- 2. 计算加速度 ----------
        # 先算最近 acceleration_period 个 ROC 值，再取 ROC 的变化率
        roc_series: List[float] = []
        for i in range(acceleration_period + 1):
            # 从倒数第 i 根K线的位置计算 ROC
            idx = -(i + 1)
            past_idx = idx - period
            if abs(past_idx) <= len(close_prices) and abs(idx) <= len(close_prices):
                p_current = close_prices[idx]
                p_past = close_prices[past_idx]
                roc_val = ((p_current - p_past) / p_past * 100) if p_past != 0 else 0.0
                roc_series.append(roc_val)

        # ROC序列是从最近到最远排列的，反转为时间正序
        roc_series.reverse()

        # 加速度 = 最新ROC - 最早ROC（即ROC的变化量）
        acceleration: float = 0.0
        if len(roc_series) >= 2:
            acceleration = roc_series[-1] - roc_series[0]

        # ---------- 3. 计算趋势一致性 ----------
        # 统计最近 period 根K线中，价格同向变动（连续涨或连续跌）的比例
        recent_closes = close_prices[-(period + 1):]
        positive_changes = 0
        negative_changes = 0

        for i in range(1, len(recent_closes)):
            price_diff = recent_closes[i] - recent_closes[i - 1]
            if price_diff > 0:
                positive_changes += 1
            elif price_diff < 0:
                negative_changes += 1

        total_changes = positive_changes + negative_changes
        # 趋势一致性 = 多数方向的占比（0.5~1.0）
        trend_consistency: float = 0.5
        if total_changes > 0:
            dominant_count = max(positive_changes, negative_changes)
            trend_consistency = dominant_count / total_changes

        # ---------- 4. 综合动量评分 ----------
        momentum_score = cls._compute_momentum_score(
            roc=roc,
            acceleration=acceleration,
            trend_consistency=trend_consistency,
        )

        return {
            "roc": round(roc, 4),
            "acceleration": round(acceleration, 4),
            "trend_consistency": round(trend_consistency, 4),
            "momentum_score": round(momentum_score, 2),
        }

    @classmethod
    def _compute_momentum_score(
        cls,
        roc: float,
        acceleration: float,
        trend_consistency: float,
    ) -> float:
        """
        将多维度指标加权合成为0-100的动量评分。

        评分逻辑：
        - ROC 贡献 50% 权重：通过 sigmoid 映射到 0-100
        - 加速度 贡献 20% 权重：正加速度加分，负加速度减分
        - 趋势一致性 贡献 30% 权重：一致性越高分数越极端

        Args:
            roc:               价格变化率（百分比）
            acceleration:      动量加速度
            trend_consistency: 趋势一致性（0-1）

        Returns:
            float: 综合评分（0-100）
        """
        # 使用 sigmoid 将 ROC 映射到 0-100，k 控制曲线陡峭度
        # ROC=0 映射到 50，ROC 越大/越小映射到越接近 100/0
        sigmoid_k = 0.3
        roc_score = 100.0 / (1.0 + math.exp(-sigmoid_k * roc))

        # 加速度分量：将加速度也通过 sigmoid 映射，幅度较小
        acc_sigmoid_k = 0.5
        acceleration_score = 100.0 / (1.0 + math.exp(-acc_sigmoid_k * acceleration))

        # 趋势一致性分量：一致性高时放大信号，低时趋向中性
        # trend_consistency 在 0.5~1.0 之间，映射到 0~100
        consistency_score = (trend_consistency - 0.5) * 200.0
        consistency_score = max(0.0, min(100.0, consistency_score))

        # 加权合成（权重比 = ROC:加速度:一致性 = 50:20:30）
        final_score = (
            roc_score * 0.50
            + acceleration_score * 0.20
            + consistency_score * 0.30
        )

        # 限制到 0-100 范围
        return max(0.0, min(100.0, final_score))

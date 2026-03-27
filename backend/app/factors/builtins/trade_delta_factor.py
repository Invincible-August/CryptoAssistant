"""
成交Delta因子模块。
基于K线数据估算买卖成交量差异（Delta），
通过价格运动方向推断主动买入/卖出比例，用于判断资金流向。
"""
import math
from typing import Any, Dict, List

from app.factors.base import BaseFactor


class TradeDeltaFactor(BaseFactor):
    """
    成交Delta因子。

    在无法获取逐笔成交数据的场景下，通过K线的开盘价和收盘价关系
    来估算主动买入和主动卖出的成交量分布。

    估算逻辑：
    - 阳线（close > open）：大部分成交量归为主动买入
    - 阴线（close < open）：大部分成交量归为主动卖出
    - 买入比例 = (close - low) / (high - low)，即价格在K线范围内的相对位置
    """

    factor_key: str = "trade_delta"
    name: str = "成交Delta因子"
    description: str = "基于K线数据估算买卖成交量Delta，判断主动买卖力量对比"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "flow"
    input_type: List[str] = ["kline"]
    score_weight: float = 1.0
    signal_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ==================== 参数定义 ====================
    params_schema: Dict[str, Any] = {
        "period": {
            "type": "int",
            "default": 20,
            "required": False,
            "description": "Delta统计回看周期（K线根数）",
            "min": 1,
            "max": 200,
        },
    }

    # ==================== 输出字段定义 ====================
    output_schema: Dict[str, Any] = {
        "buy_volume": {
            "type": "float",
            "description": "估算的主动买入成交量合计",
        },
        "sell_volume": {
            "type": "float",
            "description": "估算的主动卖出成交量合计",
        },
        "delta": {
            "type": "float",
            "description": "买卖Delta = buy_volume - sell_volume",
        },
        "delta_ratio": {
            "type": "float",
            "description": "Delta比率 = delta / total_volume（-1到1之间）",
        },
        "delta_score": {
            "type": "float",
            "description": "Delta评分（0-100），50为中性，高于50偏多，低于50偏空",
        },
    }

    # ==================== 前端展示配置 ====================
    display_config: Dict[str, Any] = {
        "chart_type": "bar",
        "primary_field": "delta",
        "score_field": "delta_score",
        "overlay": False,
        "positive_color": "#27AE60",
        "negative_color": "#E74C3C",
        "y_axis_label": "成交Delta",
    }

    @classmethod
    def calculate(cls, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算成交Delta因子。

        Args:
            context: 数据上下文，需包含 "kline" 键。
                     每根K线需包含 open、high、low、close、volume 字段。
            params:  参数字典，支持 period。

        Returns:
            Dict[str, Any]: 包含 buy_volume、sell_volume、delta、delta_ratio、delta_score
        """
        # ---------- 参数校验 ----------
        validated_params = cls.validate_params(params)
        period: int = validated_params["period"]

        # ---------- 获取K线数据 ----------
        kline_data: List[Dict[str, Any]] = context.get("kline", [])

        if len(kline_data) < period:
            return {
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "delta": 0.0,
                "delta_ratio": 0.0,
                "delta_score": 50.0,
            }

        # 取最近 period 根K线进行计算
        recent_klines = kline_data[-period:]

        total_buy_volume: float = 0.0
        total_sell_volume: float = 0.0

        for candle in recent_klines:
            open_price = float(candle["open"])
            high_price = float(candle["high"])
            low_price = float(candle["low"])
            close_price = float(candle["close"])
            volume = float(candle["volume"])

            # 计算K线振幅
            price_range = high_price - low_price

            if price_range > 0:
                # 通过收盘价在K线范围内的相对位置来估算买入比例
                # 收盘价越接近最高价，主动买入比例越大
                buy_ratio = (close_price - low_price) / price_range
            elif close_price >= open_price:
                # 十字星但收阳：55%视为买入
                buy_ratio = 0.55
            else:
                # 十字星但收阴：45%视为买入
                buy_ratio = 0.45

            # 限制 buy_ratio 在合理范围内（避免极端值）
            buy_ratio = max(0.05, min(0.95, buy_ratio))

            # 按比例分配成交量
            estimated_buy_vol = volume * buy_ratio
            estimated_sell_vol = volume * (1.0 - buy_ratio)

            total_buy_volume += estimated_buy_vol
            total_sell_volume += estimated_sell_vol

        # ---------- 计算 Delta 指标 ----------
        delta = total_buy_volume - total_sell_volume
        total_volume = total_buy_volume + total_sell_volume

        # Delta比率：标准化到 -1~1 区间
        delta_ratio: float = 0.0
        if total_volume > 0:
            delta_ratio = delta / total_volume

        # ---------- 计算 Delta 评分 ----------
        # 使用 sigmoid 将 delta_ratio（-1~1）映射到 0~100
        # delta_ratio=0 对应 50 分
        sigmoid_k = 5.0  # 控制曲线陡峭度
        delta_score = 100.0 / (1.0 + math.exp(-sigmoid_k * delta_ratio))

        return {
            "buy_volume": round(total_buy_volume, 4),
            "sell_volume": round(total_sell_volume, 4),
            "delta": round(delta, 4),
            "delta_ratio": round(delta_ratio, 6),
            "delta_score": round(max(0.0, min(100.0, delta_score)), 2),
        }

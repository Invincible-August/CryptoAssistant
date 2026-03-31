"""
主力成本区间因子模块。
通过成交量加权平均价格（VWAP）估算主力资金的持仓成本区域，
分析当前价格与主力成本区间的偏离程度，判断主力盈亏状态和潜在行为。

这是一个人工自定义因子（source=human）的完整示例。
"""
import math
from typing import Any, Dict, List

from app.factors.base import BaseFactor


class MainForceCostZoneFactor(BaseFactor):
    """
    主力成本区间因子（人工自定义因子）。

    核心思路：
    通过 VWAP 结合成交量分布估算主力资金的加权成本区间。
    当价格远离成本区间时，主力可能有"护盘"或"出货"的动机。

    计算流程：
    1. 计算 VWAP（成交量加权平均价格）作为核心成本参考
    2. 基于 VWAP 上下浮动一定比例构建成本区间
    3. 计算当前价格到 VWAP 的偏离距离
    4. 根据偏离方向和幅度输出成本优势评分

    评分解读：
    - 高分（>60）：当前价格在成本区间上方，主力处于浮盈状态
    - 中性（40-60）：价格在成本区间内，主力持仓接近成本
    - 低分（<40）：价格在成本区间下方，主力处于浮亏状态
    """

    factor_key: str = "main_force_cost_zone"
    name: str = "主力成本区间因子"
    description: str = "基于VWAP估算主力持仓成本区间，分析价格偏离和成本优势"
    source: str = "human"
    version: str = "1.0.0"
    category: str = "custom"
    input_type: List[str] = ["kline"]
    score_weight: float = 1.2
    signal_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ==================== 参数定义 ====================
    params_schema: Dict[str, Any] = {
        "period": {
            "type": "int",
            "default": 50,
            "required": False,
            "description": "VWAP计算回看周期（K线根数），较长周期反映更稳定的成本",
            "min": 10,
            "max": 500,
        },
        "zone_width": {
            "type": "float",
            "default": 0.02,
            "required": False,
            "description": "成本区间半宽度比例（相对于VWAP的百分比），0.02表示上下各2%",
            "min": 0.005,
            "max": 0.10,
        },
    }

    # ==================== 输出字段定义 ====================
    output_schema: Dict[str, Any] = {
        "vwap": {
            "type": "float",
            "description": "成交量加权平均价格，代表市场整体成本中枢",
        },
        "cost_zone_low": {
            "type": "float",
            "description": "成本区间下沿 = VWAP * (1 - zone_width)",
        },
        "cost_zone_high": {
            "type": "float",
            "description": "成本区间上沿 = VWAP * (1 + zone_width)",
        },
        "current_price": {
            "type": "float",
            "description": "当前最新收盘价",
        },
        "distance_to_vwap": {
            "type": "float",
            "description": "当前价格与VWAP的偏离百分比，正值表示价格在VWAP上方",
        },
        "cost_advantage_score": {
            "type": "float",
            "description": "成本优势评分（0-100），高于50表示多头有成本优势",
        },
    }

    # ==================== 前端展示配置 ====================
    display_config: Dict[str, Any] = {
        "chart_type": "price_zone",
        "primary_field": "vwap",
        "zone_fields": ["cost_zone_low", "cost_zone_high"],
        "overlay": True,
        "vwap_color": "#F39C12",
        "zone_color": "rgba(243, 156, 18, 0.15)",
        "zone_border_color": "rgba(243, 156, 18, 0.4)",
        "y_axis_label": "价格",
    }

    @classmethod
    def calculate(cls, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算主力成本区间因子。

        Args:
            context: 数据上下文，需包含 "kline" 键。
                     每根K线需包含 high、low、close、volume 字段。
            params:  参数字典，支持 period 和 zone_width。

        Returns:
            Dict[str, Any]: 包含 vwap、cost_zone_low、cost_zone_high、
                           current_price、distance_to_vwap、cost_advantage_score
        """
        # ---------- 参数校验 ----------
        validated_params = cls.validate_params(params)
        period: int = validated_params["period"]
        zone_width: float = validated_params["zone_width"]

        # ---------- 获取K线数据 ----------
        kline_data: List[Dict[str, Any]] = context.get("kline", [])

        # 兼容：某些路径传入 pandas.DataFrame
        try:
            import pandas as pd  # type: ignore

            if isinstance(kline_data, pd.DataFrame):
                kline_data = kline_data.to_dict("records")  # type: ignore[assignment]
        except Exception:  # noqa: BLE001
            pass

        if len(kline_data) < period:
            return cls._default_result()

        # 取最近 period 根K线
        recent_klines = kline_data[-period:]

        # ---------- 1. 计算 VWAP ----------
        # VWAP = Σ(典型价格 × 成交量) / Σ(成交量)
        # 典型价格 = (最高价 + 最低价 + 收盘价) / 3
        total_volume_price: float = 0.0
        total_volume: float = 0.0

        for candle in recent_klines:
            high_price = float(candle["high"])
            low_price = float(candle["low"])
            close_price = float(candle["close"])
            volume = float(candle["volume"])

            typical_price = (high_price + low_price + close_price) / 3.0
            total_volume_price += typical_price * volume
            total_volume += volume

        # 成交量为0时无法计算VWAP
        if total_volume == 0:
            return cls._default_result()

        vwap = total_volume_price / total_volume

        # ---------- 2. 构建成本区间 ----------
        cost_zone_low = vwap * (1.0 - zone_width)
        cost_zone_high = vwap * (1.0 + zone_width)

        # ---------- 3. 计算价格偏离 ----------
        current_price = float(kline_data[-1]["close"])
        distance_to_vwap: float = 0.0
        if vwap > 0:
            distance_to_vwap = ((current_price - vwap) / vwap) * 100

        # ---------- 4. 计算成本优势评分 ----------
        cost_advantage_score = cls._compute_cost_advantage_score(
            current_price=current_price,
            vwap=vwap,
            zone_width=zone_width,
        )

        return {
            "vwap": round(vwap, 6),
            "cost_zone_low": round(cost_zone_low, 6),
            "cost_zone_high": round(cost_zone_high, 6),
            "current_price": round(current_price, 6),
            "distance_to_vwap": round(distance_to_vwap, 4),
            "cost_advantage_score": round(cost_advantage_score, 2),
        }

    @classmethod
    def _compute_cost_advantage_score(
        cls,
        current_price: float,
        vwap: float,
        zone_width: float,
    ) -> float:
        """
        计算成本优势评分。

        评分规则：
        - 价格 = VWAP → 评分 50（中性）
        - 价格 > VWAP → 评分 > 50（多头有成本优势，主力浮盈）
        - 价格 < VWAP → 评分 < 50（多头处于成本劣势，主力浮亏）
        - 偏离幅度越大，评分越极端，但通过 sigmoid 限制在 0-100 内

        偏离幅度的标准化基准为 zone_width，即偏离一个 zone_width 时
        评分大约在 73 分（或 27 分）。

        Args:
            current_price: 当前价格
            vwap:          成交量加权平均价格
            zone_width:    成本区间半宽度比例

        Returns:
            float: 成本优势评分（0-100）
        """
        if vwap == 0:
            return 50.0

        # 标准化偏离量：将价格偏离转换为 zone_width 的倍数
        # 偏离 1 个 zone_width ≈ sigmoid 输入为 1
        deviation_ratio = (current_price - vwap) / (vwap * zone_width)

        # sigmoid 映射到 0-100
        sigmoid_k = 1.0
        score = 100.0 / (1.0 + math.exp(-sigmoid_k * deviation_ratio))

        return max(0.0, min(100.0, score))

    @classmethod
    def normalize(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将结果归一化为统一结构。

        在原始结果基础上添加：
        - factor_key: 因子标识
        - zone_position: 当前价格相对于成本区间的位置标记

        Args:
            result: calculate() 返回的原始结果

        Returns:
            Dict[str, Any]: 添加了标准化字段的结果
        """
        normalized = dict(result)
        normalized["factor_key"] = cls.factor_key

        # 标记价格相对于成本区间的位置
        current_price = result.get("current_price", 0)
        cost_zone_low = result.get("cost_zone_low", 0)
        cost_zone_high = result.get("cost_zone_high", 0)

        if current_price > cost_zone_high:
            normalized["zone_position"] = "above"    # 价格在成本区间上方
        elif current_price < cost_zone_low:
            normalized["zone_position"] = "below"    # 价格在成本区间下方
        else:
            normalized["zone_position"] = "inside"   # 价格在成本区间内

        return normalized

    @classmethod
    def format_for_signal(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换为信号分析模块可用格式。

        信号模块需要标准化的 factor_key + score + direction 结构。

        Args:
            result: 计算或归一化后的结果

        Returns:
            Dict[str, Any]: 信号模块格式
        """
        score = result.get("cost_advantage_score", 50.0)

        # 根据评分判断信号方向
        if score >= 65:
            direction = "bullish"       # 多头成本优势明显
        elif score <= 35:
            direction = "bearish"       # 多头成本劣势明显
        else:
            direction = "neutral"       # 成本区间内，方向不明

        return {
            "factor_key": cls.factor_key,
            "signal_value": score,
            "score": score,
            "direction": direction,
            "weight": cls.score_weight,
            "metadata": {
                "vwap": result.get("vwap", 0),
                "distance_to_vwap": result.get("distance_to_vwap", 0),
                "zone_position": result.get("zone_position", "unknown"),
            },
        }

    @classmethod
    def format_for_chart(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换为前端图表可展示格式。

        输出结构适配前端的价格区间叠加图（price_zone 类型）：
        - VWAP线
        - 成本区间（半透明带状区域）
        - 当前价格标记

        Args:
            result: 计算或归一化后的结果

        Returns:
            Dict[str, Any]: 前端图表组件数据格式
        """
        return {
            "chart_type": cls.display_config.get("chart_type", "price_zone"),
            "overlay": cls.display_config.get("overlay", True),
            "series": [
                {
                    "name": "VWAP",
                    "type": "line",
                    "value": result.get("vwap", 0),
                    "color": cls.display_config.get("vwap_color", "#F39C12"),
                    "dash": "solid",
                },
            ],
            "zones": [
                {
                    "name": "主力成本区间",
                    "low": result.get("cost_zone_low", 0),
                    "high": result.get("cost_zone_high", 0),
                    "fill_color": cls.display_config.get(
                        "zone_color", "rgba(243, 156, 18, 0.15)"
                    ),
                    "border_color": cls.display_config.get(
                        "zone_border_color", "rgba(243, 156, 18, 0.4)"
                    ),
                },
            ],
            "annotations": [
                {
                    "name": "当前价格",
                    "value": result.get("current_price", 0),
                    "type": "horizontal_line",
                    "color": "#3498DB",
                },
            ],
            "score": result.get("cost_advantage_score", 50.0),
            "score_label": "成本优势评分",
        }

    @classmethod
    def _default_result(cls) -> Dict[str, Any]:
        """
        返回默认结果。
        在K线数据不足时使用，保证下游模块不会因数据缺失而异常。

        Returns:
            Dict[str, Any]: 所有字段为零值/中性值的结果字典
        """
        return {
            "vwap": 0.0,
            "cost_zone_low": 0.0,
            "cost_zone_high": 0.0,
            "current_price": 0.0,
            "distance_to_vwap": 0.0,
            "cost_advantage_score": 50.0,
        }

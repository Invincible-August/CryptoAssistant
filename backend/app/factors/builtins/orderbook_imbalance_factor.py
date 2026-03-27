"""
盘口失衡因子模块。
基于订单簿（Orderbook）数据计算买卖盘挂单量失衡程度，
用于分析微观市场结构中的供需力量对比。
"""
import math
from typing import Any, Dict, List

from loguru import logger

from app.factors.base import BaseFactor


class OrderbookImbalanceFactor(BaseFactor):
    """
    盘口失衡因子。

    分析订单簿买卖双方的挂单量分布，计算失衡比率。
    当买盘挂单量远大于卖盘时，可能暗示支撑力量较强；
    反之则暗示抛压较大。

    注意：订单簿数据可能不总是可用的，因子内部做了优雅降级处理。
    """

    factor_key: str = "orderbook_imbalance"
    name: str = "盘口失衡因子"
    description: str = "分析订单簿买卖挂单量失衡程度，判断微观结构中的供需力量"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "microstructure"
    input_type: List[str] = ["orderbook"]
    score_weight: float = 0.8
    signal_compatible: bool = True
    backtest_compatible: bool = False  # 回测中通常无法获取历史订单簿快照
    ai_compatible: bool = True

    # ==================== 参数定义 ====================
    params_schema: Dict[str, Any] = {
        "depth_levels": {
            "type": "int",
            "default": 10,
            "required": False,
            "description": "参与计算的订单簿深度层级数",
            "min": 1,
            "max": 100,
        },
        "weight_decay": {
            "type": "float",
            "default": 0.9,
            "required": False,
            "description": "远离盘口的挂单权重衰减因子（0-1），越小衰减越快",
            "min": 0.1,
            "max": 1.0,
        },
    }

    # ==================== 输出字段定义 ====================
    output_schema: Dict[str, Any] = {
        "bid_total": {
            "type": "float",
            "description": "买盘加权挂单量合计",
        },
        "ask_total": {
            "type": "float",
            "description": "卖盘加权挂单量合计",
        },
        "imbalance_ratio": {
            "type": "float",
            "description": "失衡比率 = (bid - ask) / (bid + ask)，范围-1到1",
        },
        "imbalance_score": {
            "type": "float",
            "description": "失衡评分（0-100），50为均衡，高于50偏多，低于50偏空",
        },
    }

    # ==================== 前端展示配置 ====================
    display_config: Dict[str, Any] = {
        "chart_type": "gauge",
        "primary_field": "imbalance_score",
        "overlay": False,
        "color_positive": "#2ECC71",
        "color_negative": "#E74C3C",
        "color_neutral": "#95A5A6",
        "y_axis_label": "盘口失衡",
    }

    @classmethod
    def calculate(cls, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算盘口失衡因子。

        Args:
            context: 数据上下文，需包含 "orderbook" 键。
                     orderbook 结构: {"bids": [[price, qty], ...], "asks": [[price, qty], ...]}
                     bids 按价格从高到低排列，asks 按价格从低到高排列。
            params:  参数字典，支持 depth_levels 和 weight_decay。

        Returns:
            Dict[str, Any]: 包含 bid_total、ask_total、imbalance_ratio、imbalance_score
        """
        # ---------- 参数校验 ----------
        validated_params = cls.validate_params(params)
        depth_levels: int = validated_params["depth_levels"]
        weight_decay: float = validated_params["weight_decay"]

        # ---------- 获取订单簿数据 ----------
        orderbook: Dict[str, Any] = context.get("orderbook", {})

        # 优雅降级：订单簿数据不可用时返回中性默认值
        if not orderbook:
            logger.debug("盘口失衡因子: 无订单簿数据，返回中性默认值")
            return cls._default_result()

        bids: List[List[float]] = orderbook.get("bids", [])
        asks: List[List[float]] = orderbook.get("asks", [])

        if not bids or not asks:
            logger.debug("盘口失衡因子: 买盘或卖盘为空，返回中性默认值")
            return cls._default_result()

        # ---------- 计算加权挂单量 ----------
        # 对每一档挂单量施加距离衰减权重，近盘口的挂单权重更高
        bid_total = cls._weighted_volume(bids, depth_levels, weight_decay)
        ask_total = cls._weighted_volume(asks, depth_levels, weight_decay)

        # ---------- 计算失衡比率 ----------
        total_volume = bid_total + ask_total
        imbalance_ratio: float = 0.0
        if total_volume > 0:
            # 范围 -1（全是卖盘）到 1（全是买盘）
            imbalance_ratio = (bid_total - ask_total) / total_volume

        # ---------- 计算失衡评分 ----------
        # sigmoid 映射：imbalance_ratio 从 -1~1 映射到 0~100
        sigmoid_k = 4.0
        imbalance_score = 100.0 / (1.0 + math.exp(-sigmoid_k * imbalance_ratio))

        return {
            "bid_total": round(bid_total, 4),
            "ask_total": round(ask_total, 4),
            "imbalance_ratio": round(imbalance_ratio, 6),
            "imbalance_score": round(max(0.0, min(100.0, imbalance_score)), 2),
        }

    @classmethod
    def _weighted_volume(
        cls,
        orders: List[List[float]],
        depth_levels: int,
        weight_decay: float,
    ) -> float:
        """
        计算带距离衰减权重的挂单量总和。

        越远离盘口的挂单，其权重按 weight_decay^level 递减。
        这样近盘口的"真实"挂单对结果影响更大，
        减少远距离虚假挂单（spoofing）的干扰。

        Args:
            orders:       挂单列表 [[price, quantity], ...]
            depth_levels: 参与计算的层级数
            weight_decay: 每层的权重衰减系数

        Returns:
            float: 加权总挂单量
        """
        weighted_total: float = 0.0

        # 只取指定深度的层级
        levels_to_use = min(depth_levels, len(orders))

        for level_idx in range(levels_to_use):
            order = orders[level_idx]
            # 订单格式：[价格, 数量]
            quantity = float(order[1]) if len(order) >= 2 else 0.0
            # 距离衰减：第0层权重=1，第1层=decay，第2层=decay^2 ...
            weight = weight_decay ** level_idx
            weighted_total += quantity * weight

        return weighted_total

    @classmethod
    def _default_result(cls) -> Dict[str, Any]:
        """
        返回中性默认结果。
        在订单簿数据不可用时使用，避免因数据缺失导致下游异常。

        Returns:
            Dict[str, Any]: 所有字段为中性值的结果字典
        """
        return {
            "bid_total": 0.0,
            "ask_total": 0.0,
            "imbalance_ratio": 0.0,
            "imbalance_score": 50.0,
        }

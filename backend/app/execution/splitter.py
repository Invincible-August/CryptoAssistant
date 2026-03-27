"""
订单拆分模块。
支持将大额订单拆分为多个小额订单以减少市场冲击。
"""
from typing import Any, Dict, List
from decimal import Decimal
from loguru import logger


class OrderSplitter:
    """
    订单拆分器。
    支持均匀拆单和阶梯挂单两种模式。
    """

    @staticmethod
    def split_equal(
        total_quantity: float,
        num_parts: int,
        base_price: float,
        price_step: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        均匀拆单。
        将总数量平均拆分为N个子订单。

        Args:
            total_quantity: 总数量
            num_parts: 拆分数量
            base_price: 基础价格
            price_step: 每个子单的价格偏移步长

        Returns:
            子订单列表
        """
        if num_parts <= 0:
            return []

        part_qty = total_quantity / num_parts
        orders = []

        for i in range(num_parts):
            price = base_price + (i * price_step)
            orders.append(
                {
                    "index": i + 1,
                    "price": round(price, 8),
                    "quantity": round(part_qty, 8),
                    "order_type": "limit" if price_step != 0 else "market",
                }
            )

        logger.info(f"均匀拆单: 总量{total_quantity} → {num_parts}笔, 每笔{part_qty:.8f}")
        return orders

    @staticmethod
    def split_ladder(
        total_quantity: float,
        price_low: float,
        price_high: float,
        num_levels: int,
        distribution: str = "equal",
    ) -> List[Dict[str, Any]]:
        """
        阶梯挂单。
        在价格区间内按层级分布挂单。

        Args:
            total_quantity: 总数量
            price_low: 最低价
            price_high: 最高价
            num_levels: 价格层级数
            distribution: 分布方式 (equal=均匀, pyramid=金字塔)

        Returns:
            子订单列表
        """
        if num_levels <= 0 or price_low >= price_high:
            return []

        price_step = (price_high - price_low) / (num_levels - 1) if num_levels > 1 else 0

        # 计算每层的数量权重
        if distribution == "pyramid":
            # 金字塔分布：越靠近低价，数量越大
            weights = list(range(num_levels, 0, -1))
        else:
            weights = [1] * num_levels

        total_weight = sum(weights)
        orders = []

        for i in range(num_levels):
            price = price_low + (i * price_step)
            qty = total_quantity * (weights[i] / total_weight)
            orders.append(
                {
                    "index": i + 1,
                    "price": round(price, 8),
                    "quantity": round(qty, 8),
                    "order_type": "limit",
                    "level": i + 1,
                }
            )

        logger.info(
            f"阶梯挂单: 价格{price_low:.4f}~{price_high:.4f}, "
            f"{num_levels}层, 分布={distribution}"
        )
        return orders

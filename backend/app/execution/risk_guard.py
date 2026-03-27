"""
风控守卫模块。
在订单执行前进行风险检查，防止异常交易。
"""
from typing import Any, Dict
from loguru import logger


class RiskGuard:
    """
    风控守卫。
    对每笔订单进行多维度风险检查。
    """

    def __init__(
        self,
        max_single_order_value: float = 10000.0,
        max_position_value: float = 50000.0,
        max_daily_trades: int = 100,
        max_price_deviation: float = 0.05,
    ):
        self.max_single_order_value = max_single_order_value
        self.max_position_value = max_position_value
        self.max_daily_trades = max_daily_trades
        self.max_price_deviation = max_price_deviation
        self._daily_trade_count = 0

    def check_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        综合风控检查。

        Returns:
            {"passed": bool, "reason": str}
        """
        # 检查1: 单笔订单金额
        price = order.get("price", 0)
        quantity = order.get("quantity", 0)
        order_value = price * quantity

        if order_value > self.max_single_order_value:
            return {
                "passed": False,
                "reason": f"单笔订单金额{order_value:.2f}超过限制{self.max_single_order_value:.2f}",
            }

        # 检查2: 价格合理性（价格不能为0或负数）
        if price <= 0 and order.get("order_type") == "limit":
            return {"passed": False, "reason": "限价单价格不能为0或负数"}

        # 检查3: 数量合理性
        if quantity <= 0:
            return {"passed": False, "reason": "订单数量必须大于0"}

        # 检查4: 日内交易次数
        if self._daily_trade_count >= self.max_daily_trades:
            return {
                "passed": False,
                "reason": f"日内交易次数已达上限{self.max_daily_trades}",
            }

        self._daily_trade_count += 1
        return {"passed": True, "reason": ""}

    def reset_daily_counter(self):
        """重置日内交易计数器（每日0点调用）"""
        self._daily_trade_count = 0
        logger.info("风控日内计数器已重置")

    def update_config(self, **kwargs):
        """动态更新风控配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"风控参数已更新: {key} = {value}")

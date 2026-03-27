"""
订单生命周期管理模块。
管理订单的创建、跟踪、撤销和状态更新。
"""
from typing import Any, Dict, List, Optional
from loguru import logger
from app.execution.base import BaseExecutor
from app.execution.simulator import SimulatedExecutor
from app.execution.risk_guard import RiskGuard


class OrderManager:
    """
    订单管理器。
    协调执行器、风控和订单状态跟踪。
    """

    def __init__(self, executor: BaseExecutor = None):
        # 默认使用模拟执行器
        self.executor = executor or SimulatedExecutor()
        self.risk_guard = RiskGuard()
        # 活跃订单跟踪: order_id -> order_info
        self._active_orders: Dict[str, Dict[str, Any]] = {}

    async def submit_order(self, order_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        提交订单。
        先经过风控检查，再下单。

        Args:
            order_request: 订单请求，包含symbol, side, order_type, price, quantity

        Returns:
            订单结果
        """
        # 风控检查
        risk_check = self.risk_guard.check_order(order_request)
        if not risk_check["passed"]:
            logger.warning(f"订单被风控拒绝: {risk_check['reason']}")
            return {
                "status": "rejected",
                "reason": risk_check["reason"],
                "order": order_request,
            }

        try:
            result = await self.executor.place_order(order_request)
            order_id = result.get("order_id", "")

            # 跟踪活跃订单
            if result.get("status") in ("pending", "partial"):
                self._active_orders[order_id] = result

            logger.info(f"订单已提交: {order_id}, 状态={result.get('status')}")
            return result

        except Exception as e:
            logger.error(f"订单提交失败: {e}")
            return {"status": "failed", "error": str(e)}

    async def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        success = await self.executor.cancel_order(order_id)
        if success and order_id in self._active_orders:
            del self._active_orders[order_id]
        return success

    async def cancel_all(self, symbol: str = None) -> int:
        """撤销所有挂单"""
        cancelled = 0
        order_ids = list(self._active_orders.keys())

        for order_id in order_ids:
            order = self._active_orders[order_id]
            if symbol and order.get("symbol") != symbol:
                continue
            if await self.cancel_order(order_id):
                cancelled += 1

        logger.info(f"批量撤单完成: 共撤销{cancelled}笔")
        return cancelled

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """查询订单状态"""
        return await self.executor.get_order_status(order_id)

    def get_active_orders(self) -> List[Dict[str, Any]]:
        """获取所有活跃订单"""
        return list(self._active_orders.values())

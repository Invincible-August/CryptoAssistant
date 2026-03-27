"""
模拟执行器模块。
在不连接真实交易所的情况下模拟订单执行。
"""
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from loguru import logger
from app.execution.base import BaseExecutor


class SimulatedExecutor(BaseExecutor):
    """
    模拟执行器。
    用于纸上交易和测试，不连接真实交易所。
    """

    executor_name = "simulated"

    def __init__(self, slippage: float = 0.0005):
        self.slippage = slippage
        # 模拟订单簿: order_id -> order_info
        self._orders: Dict[str, Dict[str, Any]] = {}
        # 模拟成交记录
        self._fills: List[Dict[str, Any]] = []

    async def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        模拟下单。
        市价单立即成交，限价单进入挂单列表。
        """
        order_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)

        order_record = {
            "order_id": order_id,
            "symbol": order.get("symbol", ""),
            "side": order.get("side", "buy"),
            "order_type": order.get("order_type", "market"),
            "price": order.get("price", 0),
            "quantity": order.get("quantity", 0),
            "status": "pending",
            "filled_quantity": 0,
            "created_at": now.isoformat(),
        }

        # 市价单立即模拟成交
        if order_record["order_type"] == "market":
            fill_price = order_record["price"]
            if order_record["side"] == "buy":
                fill_price *= 1 + self.slippage
            else:
                fill_price *= 1 - self.slippage

            order_record["status"] = "filled"
            order_record["filled_quantity"] = order_record["quantity"]

            fill = {
                "order_id": order_id,
                "fill_price": round(fill_price, 8),
                "fill_quantity": order_record["quantity"],
                "fee": round(fill_price * order_record["quantity"] * 0.001, 8),
                "fill_time": now.isoformat(),
            }
            self._fills.append(fill)
            logger.info(f"模拟成交: {order_id}, 价格={fill_price:.8f}")
        else:
            # 限价单进入挂单列表
            order_record["status"] = "pending"

        self._orders[order_id] = order_record
        return order_record

    async def cancel_order(self, order_id: str) -> bool:
        """模拟撤单"""
        if order_id in self._orders:
            order = self._orders[order_id]
            if order["status"] == "pending":
                order["status"] = "cancelled"
                logger.info(f"模拟撤单成功: {order_id}")
                return True
        logger.warning(f"模拟撤单失败: {order_id}")
        return False

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """查询订单状态"""
        return self._orders.get(order_id, {"error": "订单不存在"})

    async def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """查询模拟挂单"""
        orders = [
            o
            for o in self._orders.values()
            if o["status"] == "pending"
        ]
        if symbol:
            orders = [o for o in orders if o["symbol"] == symbol]
        return orders

    def get_fills(self, order_id: str = None) -> List[Dict[str, Any]]:
        """查询成交记录"""
        if order_id:
            return [f for f in self._fills if f["order_id"] == order_id]
        return self._fills

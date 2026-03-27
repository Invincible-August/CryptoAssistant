"""
Binance真实交易执行器模块。
通过Binance REST API执行真实订单。
注意：默认禁用，需要显式启用才能使用。
"""
import uuid
from typing import Any, Dict, List
from loguru import logger
from app.execution.base import BaseExecutor
from app.core.config import settings


class BinanceExecutor(BaseExecutor):
    """
    Binance真实交易执行器。

    警告：此执行器会操作真实资金！
    仅在MODULE_EXECUTION_ENABLED=true且is_simulated=false时使用。
    """

    executor_name = "binance"

    def __init__(self):
        self._api_key = settings.BINANCE_API_KEY
        self._api_secret = settings.BINANCE_API_SECRET
        self._testnet = settings.BINANCE_TESTNET

        if self._testnet:
            self._base_url = "https://testnet.binance.vision"
            self._futures_url = "https://testnet.binancefuture.com"
        else:
            self._base_url = "https://api.binance.com"
            self._futures_url = "https://fapi.binance.com"

    async def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        通过Binance API下单。
        当前MVP版本返回模拟结果，真实API调用预留接口。
        """
        # TODO: 接入真实Binance API
        # 当前版本仅记录日志并返回占位结果
        logger.warning(
            f"Binance真实下单被调用（当前为占位实现）: "
            f"symbol={order.get('symbol')}, side={order.get('side')}, "
            f"qty={order.get('quantity')}"
        )

        order_id = f"BN-{uuid.uuid4().hex[:12].upper()}"
        return {
            "order_id": order_id,
            "symbol": order.get("symbol", ""),
            "side": order.get("side", ""),
            "order_type": order.get("order_type", ""),
            "price": order.get("price", 0),
            "quantity": order.get("quantity", 0),
            "status": "pending",
            "exchange_order_id": None,
            "message": "真实交易API调用预留接口，需要完成API签名集成",
        }

    async def cancel_order(self, order_id: str) -> bool:
        """撤销Binance订单（占位实现）"""
        logger.warning(f"Binance真实撤单被调用（占位实现）: {order_id}")
        return False

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """查询订单状态（占位实现）"""
        return {"order_id": order_id, "status": "unknown", "message": "占位实现"}

    async def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """查询当前挂单（占位实现）"""
        return []

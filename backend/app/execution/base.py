"""
执行器基类模块。
定义交易执行器的统一接口。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseExecutor(ABC):
    """交易执行器基类，所有执行器必须实现此接口"""

    executor_name: str = ""

    @abstractmethod
    async def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """下单"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """查询订单状态"""
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: str = None) -> list:
        """查询当前挂单"""
        pass

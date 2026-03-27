"""
交易所适配器基类模块。
定义所有交易所数据适配器的统一接口规范。
每个交易所的适配器必须继承 BaseExchangeAdapter 并实现所有抽象方法。
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
import asyncio


class BaseExchangeAdapter(ABC):
    """
    交易所数据适配器基类，所有交易所适配器必须继承此类。

    该基类定义了数据源层的统一契约，包括：
    - 连接/断开管理
    - WebSocket 实时数据订阅（K线、逐笔成交、深度）
    - REST 历史数据查询（K线、行情、订单簿、资金费率、持仓量）

    Attributes:
        exchange_name: 交易所标识名称，子类必须设置（如 "binance"）
    """

    exchange_name: str = ""

    @abstractmethod
    async def connect(self) -> None:
        """
        建立与交易所的连接。
        包括 REST 客户端初始化和 WebSocket 连接建立。
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        断开与交易所的所有连接。
        释放 WebSocket 连接和 HTTP 客户端资源。
        """
        pass

    @abstractmethod
    async def subscribe_kline(
        self, symbol: str, interval: str, callback: Callable
    ) -> None:
        """
        订阅实时K线数据流。

        Args:
            symbol: 交易对标识，如 "BTCUSDT"
            interval: K线周期，如 "1m", "5m", "1h"
            callback: 接收到数据时的回调函数，参数为 UnifiedKline
        """
        pass

    @abstractmethod
    async def subscribe_trades(self, symbol: str, callback: Callable) -> None:
        """
        订阅实时逐笔成交数据流。

        Args:
            symbol: 交易对标识
            callback: 回调函数，参数为 UnifiedTrade
        """
        pass

    @abstractmethod
    async def subscribe_depth(self, symbol: str, callback: Callable) -> None:
        """
        订阅实时深度（订单簿）数据流。

        Args:
            symbol: 交易对标识
            callback: 回调函数，参数为 UnifiedOrderbook
        """
        pass

    @abstractmethod
    async def get_klines(
        self, symbol: str, interval: str, limit: int = 500
    ) -> List[Dict]:
        """
        通过 REST 接口获取历史K线数据。

        Args:
            symbol: 交易对标识
            interval: K线周期
            limit: 返回数据条数，默认500

        Returns:
            K线数据字典列表
        """
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        """
        获取指定交易对的最新行情快照（24小时统计）。

        Args:
            symbol: 交易对标识

        Returns:
            行情数据字典
        """
        pass

    @abstractmethod
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """
        获取指定交易对的订单簿深度数据。

        Args:
            symbol: 交易对标识
            limit: 深度档位数量，默认20

        Returns:
            订单簿数据字典，包含 bids 和 asks
        """
        pass

    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> Dict:
        """
        获取永续合约的最新资金费率。

        Args:
            symbol: 交易对标识

        Returns:
            资金费率数据字典
        """
        pass

    @abstractmethod
    async def get_open_interest(self, symbol: str) -> Dict:
        """
        获取永续合约的当前全网持仓量。

        Args:
            symbol: 交易对标识

        Returns:
            持仓量数据字典
        """
        pass

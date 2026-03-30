"""
Binance 统一适配器模块。
整合 REST 客户端 + 现货 WebSocket + 合约 WebSocket，
实现 BaseExchangeAdapter 定义的完整接口。

上层调用方只需与此适配器交互，无需关心底层是通过 REST 还是 WebSocket 获取数据。
"""
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.core.enums import MarketType
from app.datafeeds.base import BaseExchangeAdapter
from app.datafeeds.exchanges.binance.parser import (
    parse_rest_agg_trades,
    parse_rest_funding,
    parse_rest_funding_rate_history,
    parse_rest_klines,
    parse_rest_open_interest,
    parse_rest_open_interest_history,
    parse_rest_orderbook,
    parse_rest_ticker,
)
from app.datafeeds.exchanges.binance.rest_client import BinanceRestClient
from app.datafeeds.exchanges.binance.spot_ws import BinanceSpotWebSocket
from app.datafeeds.exchanges.binance.futures_ws import BinanceFuturesWebSocket


class BinanceAdapter(BaseExchangeAdapter):
    """
    Binance 交易所统一适配器。

    将 REST 客户端和 WebSocket 客户端（现货 + 合约）封装为
    BaseExchangeAdapter 定义的统一接口，实现：
    - connect/disconnect: 同时管理 REST 和两个 WebSocket 的生命周期
    - subscribe_*: 根据市场类型自动路由到现货或合约 WebSocket
    - get_*: 根据市场类型调用对应的 REST API

    Attributes:
        exchange_name: 固定为 "binance"
        _rest_client: REST API 客户端实例
        _spot_ws: 现货 WebSocket 客户端实例
        _futures_ws: 合约 WebSocket 客户端实例
        _default_market_type: 默认市场类型，影响 get_* 方法的路由
    """

    exchange_name: str = "binance"

    def __init__(
        self, default_market_type: str = MarketType.SPOT.value
    ) -> None:
        """
        初始化 Binance 适配器。

        Args:
            default_market_type: 默认市场类型（"spot" 或 "perp"），
                                 当 get_* 方法未明确指定市场时使用
        """
        self._rest_client = BinanceRestClient()
        self._spot_ws = BinanceSpotWebSocket()
        self._futures_ws = BinanceFuturesWebSocket()
        self._default_market_type = default_market_type

        logger.info(
            f"Binance 适配器初始化，默认市场类型: {self._default_market_type}"
        )

    async def connect(self) -> None:
        """
        建立所有连接：REST 客户端初始化 + 现货 WebSocket + 合约 WebSocket。
        任何单个组件连接失败不阻断其他组件。
        """
        # 初始化 REST 客户端 HTTP 连接池
        try:
            await self._rest_client.init()
            logger.info("Binance REST 客户端就绪")
        except Exception as rest_error:
            logger.error(f"Binance REST 客户端初始化失败: {rest_error}")

        # 连接现货 WebSocket
        try:
            await self._spot_ws.connect()
            logger.info("Binance 现货 WebSocket 就绪")
        except Exception as spot_ws_error:
            logger.error(f"Binance 现货 WebSocket 连接失败: {spot_ws_error}")

        # 连接合约 WebSocket
        try:
            await self._futures_ws.connect()
            logger.info("Binance 合约 WebSocket 就绪")
        except Exception as futures_ws_error:
            logger.error(f"Binance 合约 WebSocket 连接失败: {futures_ws_error}")

    async def disconnect(self) -> None:
        """断开所有连接：REST + 现货 WS + 合约 WS。"""
        try:
            await self._rest_client.close()
        except Exception as rest_error:
            logger.error(f"Binance REST 客户端关闭异常: {rest_error}")

        try:
            await self._spot_ws.disconnect()
        except Exception as spot_error:
            logger.error(f"Binance 现货 WebSocket 断开异常: {spot_error}")

        try:
            await self._futures_ws.disconnect()
        except Exception as futures_error:
            logger.error(f"Binance 合约 WebSocket 断开异常: {futures_error}")

        logger.info("Binance 适配器所有连接已断开")

    # ==========================================================================
    # WebSocket 订阅接口
    # ==========================================================================

    async def subscribe_kline(
        self, symbol: str, interval: str, callback: Callable
    ) -> None:
        """
        订阅K线数据流，同时订阅现货和合约。

        Args:
            symbol: 交易对
            interval: K线周期
            callback: 回调函数
        """
        await self._spot_ws.subscribe_kline(symbol, interval, callback)
        await self._futures_ws.subscribe_kline(symbol, interval, callback)
        logger.info(f"Binance K线订阅完成: {symbol} {interval}（现货+合约）")

    async def subscribe_trades(self, symbol: str, callback: Callable) -> None:
        """
        订阅逐笔成交数据流，同时订阅现货和合约。

        Args:
            symbol: 交易对
            callback: 回调函数
        """
        await self._spot_ws.subscribe_trades(symbol, callback)
        await self._futures_ws.subscribe_trades(symbol, callback)
        logger.info(f"Binance 逐笔成交订阅完成: {symbol}（现货+合约）")

    async def subscribe_depth(self, symbol: str, callback: Callable) -> None:
        """
        订阅深度数据流，同时订阅现货和合约。

        Args:
            symbol: 交易对
            callback: 回调函数
        """
        await self._spot_ws.subscribe_depth(symbol, callback)
        await self._futures_ws.subscribe_depth(symbol, callback)
        logger.info(f"Binance 深度数据订阅完成: {symbol}（现货+合约）")

    async def subscribe_mark_price(
        self, symbol: str, callback: Callable
    ) -> None:
        """
        订阅标记价格（含资金费率）数据流，仅合约市场。

        Args:
            symbol: 交易对
            callback: 回调函数
        """
        await self._futures_ws.subscribe_mark_price(symbol, callback)
        logger.info(f"Binance 标记价格订阅完成: {symbol}（合约）")

    # ==========================================================================
    # REST 查询接口
    # ==========================================================================

    async def get_klines(
        self, symbol: str, interval: str, limit: int = 500
    ) -> List[Dict]:
        """
        获取历史K线数据，根据默认市场类型路由到现货或合约 API。

        Args:
            symbol: 交易对
            interval: K线周期
            limit: 返回条数

        Returns:
            UnifiedKline 对象列表转为字典列表
        """
        if self._default_market_type == MarketType.PERPETUAL.value:
            raw_data = await self._rest_client.get_futures_klines(
                symbol, interval, limit
            )
            market_type = "perp"
        else:
            raw_data = await self._rest_client.get_spot_klines(
                symbol, interval, limit
            )
            market_type = "spot"

        # 解析为统一结构
        unified_klines = parse_rest_klines(
            raw_data, "binance", symbol, market_type, interval
        )

        # 转换为字典列表返回，便于序列化
        return [
            {
                "exchange": k.exchange,
                "symbol": k.symbol,
                "market_type": k.market_type,
                "interval": k.interval,
                "open_time": k.open_time.isoformat(),
                "close_time": k.close_time.isoformat(),
                "open": str(k.open),
                "high": str(k.high),
                "low": str(k.low),
                "close": str(k.close),
                "volume": str(k.volume),
                "quote_volume": str(k.quote_volume),
                "trade_count": k.trade_count,
            }
            for k in unified_klines
        ]

    async def get_ticker(self, symbol: str) -> Dict:
        """
        获取最新24小时行情统计。

        Args:
            symbol: 交易对

        Returns:
            标准化行情数据字典
        """
        if self._default_market_type == MarketType.PERPETUAL.value:
            raw_data = await self._rest_client.get_futures_ticker_24hr(symbol)
        else:
            raw_data = await self._rest_client.get_spot_ticker_24hr(symbol)

        return parse_rest_ticker(raw_data)

    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """
        获取订单簿深度数据。

        Args:
            symbol: 交易对
            limit: 深度档位数

        Returns:
            标准化订单簿数据字典
        """
        market_type = self._default_market_type

        if market_type == MarketType.PERPETUAL.value:
            raw_data = await self._rest_client.get_futures_orderbook(
                symbol, limit
            )
            mt = "perp"
        else:
            raw_data = await self._rest_client.get_spot_orderbook(symbol, limit)
            mt = "spot"

        unified_ob = parse_rest_orderbook(raw_data, "binance", symbol, mt)

        return {
            "exchange": unified_ob.exchange,
            "symbol": unified_ob.symbol,
            "market_type": unified_ob.market_type,
            "snapshot_time": unified_ob.snapshot_time.isoformat(),
            "bids": [
                [str(price), str(qty)] for price, qty in unified_ob.bids
            ],
            "asks": [
                [str(price), str(qty)] for price, qty in unified_ob.asks
            ],
        }

    async def get_funding_rate(self, symbol: str) -> Dict:
        """
        获取永续合约最新资金费率。

        Args:
            symbol: 交易对

        Returns:
            标准化资金费率数据字典
        """
        raw_data = await self._rest_client.get_funding_rate(symbol)
        unified_funding = parse_rest_funding(raw_data, "binance")

        return {
            "exchange": unified_funding.exchange,
            "symbol": unified_funding.symbol,
            "funding_rate": str(unified_funding.funding_rate),
            "funding_time": unified_funding.funding_time.isoformat(),
            "next_funding_time": (
                unified_funding.next_funding_time.isoformat()
                if unified_funding.next_funding_time
                else None
            ),
        }

    async def get_open_interest(self, symbol: str) -> Dict:
        """
        获取永续合约当前全网持仓量。

        Args:
            symbol: 交易对

        Returns:
            标准化持仓量数据字典
        """
        raw_data = await self._rest_client.get_open_interest(symbol)
        unified_oi = parse_rest_open_interest(raw_data, "binance", symbol)

        return {
            "exchange": unified_oi.exchange,
            "symbol": unified_oi.symbol,
            "market_type": unified_oi.market_type,
            "open_interest": str(unified_oi.open_interest),
            "event_time": unified_oi.event_time.isoformat(),
        }

    async def get_spot_agg_trades_history(
        self,
        symbol: str,
        start_time: int,
        end_time: int,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical spot aggregate trades and return normalized dict rows.

        Args:
            symbol: Trading pair.
            start_time: Window start (ms).
            end_time: Window end (ms).
            limit: Max trades per request (capped by Binance).
            use_proxy: Forwarded to REST client when proxy env vars are set.

        Returns:
            List of serializable trade dictionaries.
        """
        raw = await self._rest_client.get_spot_agg_trades(
            symbol,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            use_proxy=use_proxy,
        )
        trades = parse_rest_agg_trades(raw, "binance", symbol, "spot")
        return [
            {
                "exchange": t.exchange,
                "symbol": t.symbol,
                "market_type": t.market_type,
                "trade_id": t.trade_id,
                "price": str(t.price),
                "quantity": str(t.quantity),
                "side": t.side,
                "event_time": t.event_time.isoformat(),
            }
            for t in trades
        ]

    async def get_futures_agg_trades_history(
        self,
        symbol: str,
        start_time: int,
        end_time: int,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical USDT-M futures aggregate trades as normalized dict rows.

        Args:
            symbol: Trading pair.
            start_time: Window start (ms).
            end_time: Window end (ms).
            limit: Max trades per request.
            use_proxy: Forwarded to REST client when proxy env vars are set.

        Returns:
            List of serializable trade dictionaries.
        """
        raw = await self._rest_client.get_futures_agg_trades(
            symbol,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            use_proxy=use_proxy,
        )
        trades = parse_rest_agg_trades(raw, "binance", symbol, "perp")
        return [
            {
                "exchange": t.exchange,
                "symbol": t.symbol,
                "market_type": t.market_type,
                "trade_id": t.trade_id,
                "price": str(t.price),
                "quantity": str(t.quantity),
                "side": t.side,
                "event_time": t.event_time.isoformat(),
            }
            for t in trades
        ]

    async def get_funding_rate_history(
        self,
        symbol: str,
        start_time: int,
        end_time: int,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical funding rates for a perpetual symbol.

        Args:
            symbol: Trading pair.
            start_time: Window start (ms).
            end_time: Window end (ms).
            limit: Max rows per request.
            use_proxy: Forwarded to REST client when proxy env vars are set.

        Returns:
            List of normalized funding rate dicts.
        """
        raw = await self._rest_client.get_funding_rate_history(
            symbol,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            use_proxy=use_proxy,
        )
        return parse_rest_funding_rate_history(raw, "binance")

    async def get_open_interest_history(
        self,
        symbol: str,
        period: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical open interest statistics (aggregated by ``period``).

        Args:
            symbol: Trading pair.
            period: Binance aggregation window (e.g. ``1h``, ``1d``).
            start_time: Window start (ms), optional.
            end_time: Window end (ms), optional.
            limit: Max rows per request.
            use_proxy: Forwarded to REST client when proxy env vars are set.

        Returns:
            List of normalized open interest history dicts.
        """
        raw = await self._rest_client.get_open_interest_history(
            symbol,
            period=period,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
            use_proxy=use_proxy,
        )
        return parse_rest_open_interest_history(raw, "binance")

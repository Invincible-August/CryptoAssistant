"""
Binance 合约 WebSocket 客户端模块。
连接 Binance U本位永续合约 WebSocket 流，
订阅K线、逐笔成交、深度、标记价格（含资金费率）等数据。
内置自动重连、心跳检测和消息解析逻辑。
"""
import asyncio
import json
import inspect
from typing import Any, Callable, Dict, Optional, Set

import websockets
from websockets.exceptions import ConnectionClosed
from loguru import logger

from app.core.config import settings
from app.datafeeds.exchanges.binance.parser import (
    parse_ws_depth,
    parse_ws_kline,
    parse_ws_mark_price,
    parse_ws_trade,
)


# ==================== Binance 合约 WebSocket 地址 ====================
_FUTURES_WS_URL = "wss://fstream.binance.com/ws"
_FUTURES_WS_TESTNET_URL = "wss://stream.binancefuture.com/ws"

# 单个连接最大订阅流数量
_MAX_STREAMS_PER_CONNECTION = 200

# 心跳间隔（秒）
_HEARTBEAT_INTERVAL = 30


class BinanceFuturesWebSocket:
    """
    Binance U本位合约 WebSocket 客户端。

    相比现货 WebSocket，合约额外支持：
    - 标记价格（markPrice）流：实时资金费率信息
    - 聚合成交（aggTrade）流：合约使用聚合成交而非逐笔成交

    Attributes:
        _ws_url: WebSocket 连接地址
        _ws: WebSocket 连接实例
        _callbacks: 回调函数注册表 {stream_name: callback}
        _subscribed_streams: 已订阅的流名称集合
        _is_running: 运行状态标志
        _listen_task: 消息监听协程任务
        _heartbeat_task: 心跳保活协程任务
        _reconnect_delay: 重连延迟（秒）
        _subscription_id: 订阅请求自增 ID
    """

    def __init__(self) -> None:
        """初始化合约 WebSocket 客户端。"""
        self._ws_url = (
            _FUTURES_WS_TESTNET_URL
            if settings.BINANCE_TESTNET
            else _FUTURES_WS_URL
        )
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._callbacks: Dict[str, Callable] = {}
        self._subscribed_streams: Set[str] = set()
        self._is_running: bool = False
        self._listen_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_delay: float = 5.0
        self._subscription_id: int = 0

        logger.info(f"Binance 合约 WebSocket 初始化，地址: {self._ws_url}")

    async def connect(self) -> None:
        """
        建立 WebSocket 连接并启动消息监听和心跳任务。

        Raises:
            ConnectionError: 无法建立连接时
        """
        try:
            connect_kwargs: Dict[str, Any] = {
                "ping_interval": 20,
                "ping_timeout": 10,
                "max_size": 10 * 1024 * 1024,
            }

            # 代理支持由 settings 控制；仅在当前 websockets 版本支持 `proxy` 参数时传入。
            if settings.BINANCE_PROXY_ENABLED and settings.BINANCE_PROXY_URL:
                if "proxy" in inspect.signature(websockets.connect).parameters:
                    connect_kwargs["proxy"] = settings.BINANCE_PROXY_URL
                else:
                    raise RuntimeError(
                        "当前 websockets 版本不支持 `proxy=` 参数，"
                        "请升级 backend/requirements.txt 中 websockets 版本以启用 WebSocket 代理。"
                    )

            self._ws = await websockets.connect(self._ws_url, **connect_kwargs)
            self._is_running = True

            self._listen_task = asyncio.create_task(self._listen_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("Binance 合约 WebSocket 连接成功")
        except Exception as connect_error:
            logger.error(f"Binance 合约 WebSocket 连接失败: {connect_error}")
            raise ConnectionError(
                f"无法连接 Binance 合约 WebSocket: {connect_error}"
            )

    async def disconnect(self) -> None:
        """断开 WebSocket 连接，取消所有后台任务。"""
        self._is_running = False

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        logger.info("Binance 合约 WebSocket 已断开")

    async def subscribe_kline(
        self, symbol: str, interval: str, callback: Callable
    ) -> None:
        """
        订阅合约K线数据流。

        Args:
            symbol: 交易对
            interval: K线周期
            callback: 回调函数
        """
        stream_name = f"{symbol.lower()}@kline_{interval}"
        await self._subscribe_stream(stream_name, callback)

    async def subscribe_trades(self, symbol: str, callback: Callable) -> None:
        """
        订阅合约聚合成交数据流。
        合约市场使用 aggTrade 而非 trade 流，聚合了同价格同方向的成交。

        Args:
            symbol: 交易对
            callback: 回调函数
        """
        # 合约市场使用 aggTrade 流
        stream_name = f"{symbol.lower()}@aggTrade"
        await self._subscribe_stream(stream_name, callback)

    async def subscribe_depth(self, symbol: str, callback: Callable) -> None:
        """
        订阅合约深度数据流。

        Args:
            symbol: 交易对
            callback: 回调函数
        """
        stream_name = f"{symbol.lower()}@depth@100ms"
        await self._subscribe_stream(stream_name, callback)

    async def subscribe_mark_price(
        self, symbol: str, callback: Callable
    ) -> None:
        """
        订阅标记价格流（包含实时资金费率）。
        每3秒推送一次，包含标记价格、资金费率和下次结算时间。

        Args:
            symbol: 交易对
            callback: 回调函数，接收 UnifiedFunding 对象
        """
        stream_name = f"{symbol.lower()}@markPrice@1s"
        await self._subscribe_stream(stream_name, callback)

    async def _subscribe_stream(
        self, stream_name: str, callback: Callable
    ) -> None:
        """
        向 Binance 合约 WebSocket 发送订阅请求。

        Args:
            stream_name: 流名称
            callback: 回调函数
        """
        if stream_name in self._subscribed_streams:
            logger.warning(f"合约 WebSocket 流已订阅，跳过: {stream_name}")
            return

        if len(self._subscribed_streams) >= _MAX_STREAMS_PER_CONNECTION:
            logger.error(
                f"合约 WebSocket 订阅流数量已达上限 "
                f"({_MAX_STREAMS_PER_CONNECTION})，无法订阅: {stream_name}"
            )
            return

        self._callbacks[stream_name] = callback
        self._subscribed_streams.add(stream_name)

        if self._ws:
            self._subscription_id += 1
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [stream_name],
                "id": self._subscription_id,
            }
            try:
                await self._ws.send(json.dumps(subscribe_message))
                logger.info(f"合约 WebSocket 订阅发送成功: {stream_name}")
            except Exception as send_error:
                logger.error(
                    f"合约 WebSocket 订阅发送失败: {stream_name} - {send_error}"
                )

    async def _listen_loop(self) -> None:
        """
        WebSocket 消息监听主循环。
        持续接收消息并分发到对应的回调函数。
        """
        while self._is_running:
            try:
                if not self._ws:
                    await asyncio.sleep(1)
                    continue

                raw_message = await self._ws.recv()
                data = json.loads(raw_message)

                # 忽略订阅确认响应
                if "result" in data:
                    continue

                await self._dispatch_message(data)

            except ConnectionClosed as close_error:
                logger.warning(
                    f"合约 WebSocket 连接关闭: code={close_error.code} "
                    f"reason={close_error.reason}"
                )
                if self._is_running:
                    await self._reconnect()

            except asyncio.CancelledError:
                break

            except json.JSONDecodeError as json_error:
                logger.warning(f"合约 WebSocket 消息 JSON 解析失败: {json_error}")

            except Exception as unexpected_error:
                logger.error(
                    f"合约 WebSocket 监听循环异常: {unexpected_error}",
                    exc_info=True,
                )
                if self._is_running:
                    await asyncio.sleep(1)

    async def _dispatch_message(self, data: Dict[str, Any]) -> None:
        """
        根据消息事件类型将数据分发到对应的回调函数。

        合约 WebSocket 支持的事件类型：
        - "kline": K线事件
        - "aggTrade": 聚合成交事件（合约特有）
        - "depthUpdate": 深度增量更新
        - "markPriceUpdate": 标记价格更新（含资金费率）

        Args:
            data: 解析后的 JSON 消息字典
        """
        event_type = data.get("e", "")

        try:
            if event_type == "kline":
                kline_data = data.get("k", {})
                stream_name = (
                    f"{data.get('s', '').lower()}"
                    f"@kline_{kline_data.get('i', '')}"
                )
                callback = self._callbacks.get(stream_name)
                if callback:
                    unified_kline = parse_ws_kline(data, "binance", "perp")
                    await self._invoke_callback(callback, unified_kline)

            elif event_type == "aggTrade":
                stream_name = f"{data.get('s', '').lower()}@aggTrade"
                callback = self._callbacks.get(stream_name)
                if callback:
                    unified_trade = parse_ws_trade(data, "binance", "perp")
                    await self._invoke_callback(callback, unified_trade)

            elif event_type == "depthUpdate":
                symbol_lower = data.get("s", "").lower()
                for stream_key in [
                    f"{symbol_lower}@depth@100ms",
                    f"{symbol_lower}@depth",
                ]:
                    callback = self._callbacks.get(stream_key)
                    if callback:
                        unified_depth = parse_ws_depth(data, "binance", "perp")
                        await self._invoke_callback(callback, unified_depth)
                        break

            elif event_type == "markPriceUpdate":
                # 标记价格流名称可能带不同的推送频率后缀
                symbol_lower = data.get("s", "").lower()
                for stream_key in [
                    f"{symbol_lower}@markPrice@1s",
                    f"{symbol_lower}@markPrice",
                ]:
                    callback = self._callbacks.get(stream_key)
                    if callback:
                        unified_funding = parse_ws_mark_price(data, "binance")
                        await self._invoke_callback(callback, unified_funding)
                        break

        except Exception as dispatch_error:
            logger.error(
                f"合约 WebSocket 消息分发处理异常: {dispatch_error}",
                exc_info=True,
            )

    async def _invoke_callback(self, callback: Callable, data: Any) -> None:
        """
        安全地调用回调函数。

        Args:
            callback: 回调函数
            data: 传递给回调的数据对象
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(data)
            else:
                callback(data)
        except Exception as callback_error:
            logger.error(f"合约 WebSocket 回调执行异常: {callback_error}")

    async def _heartbeat_loop(self) -> None:
        """心跳保活循环，防止连接因空闲被断开。"""
        while self._is_running:
            try:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                if self._ws:
                    await self._ws.pong()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def _reconnect(self) -> None:
        """
        执行一次重连操作。
        重连成功后自动重新发送所有订阅请求。
        """
        logger.info(
            f"合约 WebSocket 准备重连，等待 {self._reconnect_delay} 秒..."
        )
        await asyncio.sleep(self._reconnect_delay)

        try:
            if self._ws:
                try:
                    await self._ws.close()
                except Exception:
                    pass

            self._ws = await websockets.connect(
                self._ws_url,
                ping_interval=20,
                ping_timeout=10,
                max_size=10 * 1024 * 1024,
            )
            logger.info("合约 WebSocket 重连成功")

            # 重新订阅所有流
            if self._subscribed_streams:
                self._subscription_id += 1
                resubscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": list(self._subscribed_streams),
                    "id": self._subscription_id,
                }
                await self._ws.send(json.dumps(resubscribe_message))
                logger.info(
                    f"合约 WebSocket 重新订阅 {len(self._subscribed_streams)} 个流"
                )

            self._reconnect_delay = 5.0

        except Exception as reconnect_error:
            logger.error(f"合约 WebSocket 重连失败: {reconnect_error}")
            self._reconnect_delay = min(self._reconnect_delay * 2, 60.0)

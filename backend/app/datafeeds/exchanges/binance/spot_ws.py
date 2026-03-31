"""
Binance 现货 WebSocket 客户端模块。
连接 Binance 现货 WebSocket 流，订阅实时K线、逐笔成交和深度数据。
内置自动重连、心跳检测和消息解析逻辑。
"""
import asyncio
import json
import inspect
from typing import Any, Callable, Dict, List, Optional, Set

import websockets
from websockets.exceptions import ConnectionClosed
from loguru import logger

from app.core.config import settings
from app.datafeeds.exchanges.binance.parser import (
    parse_ws_depth,
    parse_ws_kline,
    parse_ws_trade,
)


# ==================== Binance 现货 WebSocket 地址 ====================
_SPOT_WS_URL = "wss://stream.binance.com:9443/ws"
_SPOT_WS_TESTNET_URL = "wss://stream.testnet.binance.vision/ws"

# 单个连接最大订阅流数量（Binance 限制每个连接最多200个流）
_MAX_STREAMS_PER_CONNECTION = 200

# WebSocket Ping/Pong 心跳间隔（秒）
_HEARTBEAT_INTERVAL = 30


class BinanceSpotWebSocket:
    """
    Binance 现货 WebSocket 客户端。

    通过单连接多流方式订阅实时行情数据，支持：
    - K线（kline）数据流
    - 逐笔成交（trade）数据流
    - 深度（depth）数据流
    - 自动重连和心跳保活
    - 消息解析并分发到注册的回调函数

    Attributes:
        _ws_url: WebSocket 连接地址
        _ws: WebSocket 连接实例
        _callbacks: 回调函数注册表 {stream_name: callback}
        _subscribed_streams: 已订阅的流名称集合
        _is_running: 运行状态标志
        _listen_task: 消息监听协程任务
        _heartbeat_task: 心跳发送协程任务
        _reconnect_delay: 重连延迟（秒）
        _subscription_id: 订阅请求自增 ID
    """

    def __init__(self) -> None:
        """初始化 WebSocket 客户端，根据配置选择正式/测试网地址。"""
        self._ws_url = (
            _SPOT_WS_TESTNET_URL
            if settings.BINANCE_TESTNET
            else _SPOT_WS_URL
        )
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        # {流名称: 回调函数} 例如 {"btcusdt@kline_1m": on_kline_callback}
        self._callbacks: Dict[str, Callable] = {}
        self._subscribed_streams: Set[str] = set()
        self._is_running: bool = False
        self._listen_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_delay: float = 5.0
        self._subscription_id: int = 0

        logger.info(f"Binance 现货 WebSocket 初始化，地址: {self._ws_url}")

    async def connect(self) -> None:
        """
        建立 WebSocket 连接并启动消息监听和心跳任务。

        Raises:
            ConnectionError: 无法建立 WebSocket 连接时
        """
        try:
            connect_kwargs: Dict[str, Any] = {
                "ping_interval": 20,
                "ping_timeout": 10,
                # 限制单条消息最大为 10MB，防止异常数据占用过多内存
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

            # 启动后台消息监听协程
            self._listen_task = asyncio.create_task(self._listen_loop())
            # 启动心跳保活协程
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info("Binance 现货 WebSocket 连接成功")
        except Exception as connect_error:
            logger.error(f"Binance 现货 WebSocket 连接失败: {connect_error}")
            raise ConnectionError(
                f"无法连接 Binance 现货 WebSocket: {connect_error}"
            )

    async def disconnect(self) -> None:
        """断开 WebSocket 连接，取消所有后台任务。"""
        self._is_running = False

        # 取消心跳任务
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

        # 取消监听任务
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()

        # 关闭 WebSocket 连接
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        logger.info("Binance 现货 WebSocket 已断开")

    async def subscribe_kline(
        self, symbol: str, interval: str, callback: Callable
    ) -> None:
        """
        订阅K线数据流。

        Args:
            symbol: 交易对（如 "BTCUSDT"）
            interval: K线周期（如 "1m", "5m", "1h"）
            callback: 接收 UnifiedKline 对象的回调函数
        """
        # Binance WebSocket 流名称格式：{symbol小写}@kline_{interval}
        stream_name = f"{symbol.lower()}@kline_{interval}"
        await self._subscribe_stream(stream_name, callback)

    async def subscribe_trades(self, symbol: str, callback: Callable) -> None:
        """
        订阅逐笔成交数据流。

        Args:
            symbol: 交易对
            callback: 接收 UnifiedTrade 对象的回调函数
        """
        stream_name = f"{symbol.lower()}@trade"
        await self._subscribe_stream(stream_name, callback)

    async def subscribe_depth(self, symbol: str, callback: Callable) -> None:
        """
        订阅深度数据流（每100ms推送一次增量变更）。

        Args:
            symbol: 交易对
            callback: 接收 UnifiedOrderbook 对象的回调函数
        """
        # depth@100ms 提供100毫秒一次的深度增量推送
        stream_name = f"{symbol.lower()}@depth@100ms"
        await self._subscribe_stream(stream_name, callback)

    async def _subscribe_stream(
        self, stream_name: str, callback: Callable
    ) -> None:
        """
        向 Binance WebSocket 发送订阅请求。

        Args:
            stream_name: Binance 流名称
            callback: 该流对应的数据回调函数
        """
        if stream_name in self._subscribed_streams:
            logger.warning(f"现货 WebSocket 流已订阅，跳过: {stream_name}")
            return

        if len(self._subscribed_streams) >= _MAX_STREAMS_PER_CONNECTION:
            logger.error(
                f"现货 WebSocket 订阅流数量已达上限 "
                f"({_MAX_STREAMS_PER_CONNECTION})，无法订阅: {stream_name}"
            )
            return

        # 注册回调
        self._callbacks[stream_name] = callback
        self._subscribed_streams.add(stream_name)

        # 如果连接已建立，立即发送订阅请求
        if self._ws:
            self._subscription_id += 1
            subscribe_message = {
                "method": "SUBSCRIBE",
                "params": [stream_name],
                "id": self._subscription_id,
            }
            try:
                await self._ws.send(json.dumps(subscribe_message))
                logger.info(f"现货 WebSocket 订阅发送成功: {stream_name}")
            except Exception as send_error:
                logger.error(
                    f"现货 WebSocket 订阅发送失败: {stream_name} - {send_error}"
                )

    async def _listen_loop(self) -> None:
        """
        WebSocket 消息监听主循环。
        持续接收消息并分发到对应的回调函数。
        连接断开时自动触发重连。
        """
        while self._is_running:
            try:
                if not self._ws:
                    await asyncio.sleep(1)
                    continue

                # 等待并接收下一条 WebSocket 消息
                raw_message = await self._ws.recv()
                data = json.loads(raw_message)

                # 忽略订阅确认响应（带有 "result" 字段）
                if "result" in data:
                    continue

                # 根据消息中的 stream 或 event 类型分发处理
                await self._dispatch_message(data)

            except ConnectionClosed as close_error:
                logger.warning(
                    f"现货 WebSocket 连接关闭: code={close_error.code} "
                    f"reason={close_error.reason}"
                )
                if self._is_running:
                    await self._reconnect()

            except asyncio.CancelledError:
                # 任务被取消，正常退出
                break

            except json.JSONDecodeError as json_error:
                logger.warning(f"现货 WebSocket 消息 JSON 解析失败: {json_error}")

            except Exception as unexpected_error:
                logger.error(
                    f"现货 WebSocket 监听循环异常: {unexpected_error}",
                    exc_info=True,
                )
                if self._is_running:
                    await asyncio.sleep(1)

    async def _dispatch_message(self, data: Dict[str, Any]) -> None:
        """
        根据消息内容将数据分发到对应的回调函数。

        Binance 推送的消息通过事件类型（"e" 字段）区分：
        - "kline": K线事件
        - "trade": 逐笔成交事件
        - "depthUpdate": 深度增量更新事件

        Args:
            data: 解析后的 JSON 消息字典
        """
        event_type = data.get("e", "")

        try:
            if event_type == "kline":
                # 构造流名称用于查找回调
                kline_data = data.get("k", {})
                stream_name = (
                    f"{data.get('s', '').lower()}"
                    f"@kline_{kline_data.get('i', '')}"
                )
                callback = self._callbacks.get(stream_name)
                if callback:
                    unified_kline = parse_ws_kline(data, "binance", "spot")
                    await self._invoke_callback(callback, unified_kline)

            elif event_type == "trade":
                stream_name = f"{data.get('s', '').lower()}@trade"
                callback = self._callbacks.get(stream_name)
                if callback:
                    unified_trade = parse_ws_trade(data, "binance", "spot")
                    await self._invoke_callback(callback, unified_trade)

            elif event_type == "depthUpdate":
                # 深度流可能有不同的推送频率后缀
                symbol_lower = data.get("s", "").lower()
                # 尝试匹配多种深度流名称格式
                for stream_key in [
                    f"{symbol_lower}@depth@100ms",
                    f"{symbol_lower}@depth",
                ]:
                    callback = self._callbacks.get(stream_key)
                    if callback:
                        unified_depth = parse_ws_depth(data, "binance", "spot")
                        await self._invoke_callback(callback, unified_depth)
                        break

        except Exception as dispatch_error:
            logger.error(
                f"现货 WebSocket 消息分发处理异常: {dispatch_error}",
                exc_info=True,
            )

    async def _invoke_callback(self, callback: Callable, data: Any) -> None:
        """
        安全地调用回调函数，支持同步和异步回调。

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
            logger.error(f"现货 WebSocket 回调执行异常: {callback_error}")

    async def _heartbeat_loop(self) -> None:
        """
        心跳保活循环。
        定期向 Binance 发送 pong 帧，防止连接因空闲被断开。
        """
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
        重连成功后自动重新发送所有之前的流订阅请求。
        """
        logger.info(
            f"现货 WebSocket 准备重连，等待 {self._reconnect_delay} 秒..."
        )
        await asyncio.sleep(self._reconnect_delay)

        try:
            # 关闭旧连接
            if self._ws:
                try:
                    await self._ws.close()
                except Exception:
                    pass

            # 建立新连接
            self._ws = await websockets.connect(
                self._ws_url,
                ping_interval=20,
                ping_timeout=10,
                max_size=10 * 1024 * 1024,
            )
            logger.info("现货 WebSocket 重连成功")

            # 重新发送所有订阅请求
            if self._subscribed_streams:
                self._subscription_id += 1
                resubscribe_message = {
                    "method": "SUBSCRIBE",
                    "params": list(self._subscribed_streams),
                    "id": self._subscription_id,
                }
                await self._ws.send(json.dumps(resubscribe_message))
                logger.info(
                    f"现货 WebSocket 重新订阅 {len(self._subscribed_streams)} 个流"
                )

            # 重连成功后重置延迟
            self._reconnect_delay = 5.0

        except Exception as reconnect_error:
            logger.error(f"现货 WebSocket 重连失败: {reconnect_error}")
            # 指数退避，最大60秒
            self._reconnect_delay = min(self._reconnect_delay * 2, 60.0)

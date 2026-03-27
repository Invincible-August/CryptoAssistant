"""
数据源管理器模块。
统一管理所有交易所适配器实例的生命周期、订阅关系和重连逻辑。
作为数据源层的顶层编排器，向上游提供简洁的订阅/取消订阅接口。
"""
import asyncio
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from loguru import logger

from app.datafeeds.base import BaseExchangeAdapter


class DatafeedManager:
    """
    数据源管理器。

    职责：
    1. 管理多个交易所适配器实例的注册与获取
    2. 统一处理数据流订阅/取消订阅请求
    3. 维护订阅关系映射表，便于批量管理
    4. 提供自动重连机制，保障 WebSocket 连接稳定性

    Attributes:
        _adapters: 已注册的交易所适配器字典 {exchange_name: adapter_instance}
        _subscriptions: 活跃订阅记录集合，每条为 (exchange, stream_type, symbol, interval)
        _reconnect_delay_seconds: 重连基础延迟秒数
        _max_reconnect_delay_seconds: 重连最大延迟秒数（指数退避上限）
        _reconnect_tasks: 正在执行的重连任务字典
        _is_running: 管理器运行状态标志
    """

    def __init__(
        self,
        reconnect_delay_seconds: float = 5.0,
        max_reconnect_delay_seconds: float = 300.0,
    ) -> None:
        """
        初始化数据源管理器。

        Args:
            reconnect_delay_seconds: 首次重连等待时间（秒）
            max_reconnect_delay_seconds: 指数退避最大等待时间（秒）
        """
        self._adapters: Dict[str, BaseExchangeAdapter] = {}
        # 订阅记录：(交易所名称, 数据流类型, 交易对, 周期/空字符串)
        self._subscriptions: Set[Tuple[str, str, str, str]] = set()
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._max_reconnect_delay_seconds = max_reconnect_delay_seconds
        # 每个交易所的重连协程任务
        self._reconnect_tasks: Dict[str, asyncio.Task] = {}
        self._is_running: bool = False

    def register_adapter(self, adapter: BaseExchangeAdapter) -> None:
        """
        注册一个交易所适配器实例。

        Args:
            adapter: 继承自 BaseExchangeAdapter 的适配器实例

        Raises:
            ValueError: 当适配器的 exchange_name 为空时
        """
        if not adapter.exchange_name:
            raise ValueError("适配器的 exchange_name 不能为空")

        self._adapters[adapter.exchange_name] = adapter
        logger.info(f"数据源适配器已注册: {adapter.exchange_name}")

    def get_adapter(self, exchange_name: str) -> Optional[BaseExchangeAdapter]:
        """
        根据交易所名称获取已注册的适配器实例。

        Args:
            exchange_name: 交易所标识

        Returns:
            适配器实例，未注册则返回 None
        """
        return self._adapters.get(exchange_name)

    def list_adapters(self) -> List[str]:
        """
        列出所有已注册的交易所适配器名称。

        Returns:
            交易所名称列表
        """
        return list(self._adapters.keys())

    async def connect_all(self) -> None:
        """
        启动所有已注册适配器的连接。
        任何单个适配器连接失败不影响其他适配器，仅记录错误日志。
        """
        self._is_running = True
        for name, adapter in self._adapters.items():
            try:
                await adapter.connect()
                logger.info(f"交易所适配器连接成功: {name}")
            except Exception as connect_error:
                logger.error(f"交易所适配器连接失败: {name} - {connect_error}")
                # 连接失败时启动后台重连任务
                self._schedule_reconnect(name)

    async def disconnect_all(self) -> None:
        """
        断开所有已注册适配器的连接，并取消所有重连任务。
        """
        self._is_running = False

        # 先取消所有正在进行的重连任务
        for name, task in self._reconnect_tasks.items():
            task.cancel()
            logger.info(f"已取消交易所 {name} 的重连任务")
        self._reconnect_tasks.clear()

        # 逐个断开适配器连接
        for name, adapter in self._adapters.items():
            try:
                await adapter.disconnect()
                logger.info(f"交易所适配器已断开: {name}")
            except Exception as disconnect_error:
                logger.error(f"交易所适配器断开失败: {name} - {disconnect_error}")

        # 清空订阅记录
        self._subscriptions.clear()

    async def subscribe(
        self,
        exchange_name: str,
        stream_type: str,
        symbol: str,
        callback: Callable,
        interval: str = "",
    ) -> None:
        """
        订阅指定交易所的数据流。

        根据 stream_type 分发到适配器的对应订阅方法。

        Args:
            exchange_name: 交易所标识
            stream_type: 数据流类型（"kline" / "trades" / "depth"）
            symbol: 交易对
            callback: 数据回调函数
            interval: K线周期（仅 stream_type="kline" 时需要）

        Raises:
            ValueError: 交易所未注册或数据流类型不支持
        """
        adapter = self._adapters.get(exchange_name)
        if not adapter:
            raise ValueError(f"交易所适配器未注册: {exchange_name}")

        # 根据数据流类型路由到不同的订阅方法
        match stream_type:
            case "kline":
                if not interval:
                    raise ValueError("订阅K线数据流必须指定 interval 参数")
                await adapter.subscribe_kline(symbol, interval, callback)
            case "trades":
                await adapter.subscribe_trades(symbol, callback)
            case "depth":
                await adapter.subscribe_depth(symbol, callback)
            case _:
                raise ValueError(
                    f"不支持的数据流类型: {stream_type}，"
                    f"可选值: kline / trades / depth"
                )

        # 记录订阅关系
        subscription_key = (exchange_name, stream_type, symbol, interval)
        self._subscriptions.add(subscription_key)
        logger.info(
            f"数据流订阅成功: {exchange_name} {stream_type} "
            f"{symbol} {interval or ''}"
        )

    async def unsubscribe(
        self,
        exchange_name: str,
        stream_type: str,
        symbol: str,
        interval: str = "",
    ) -> None:
        """
        取消订阅指定数据流。
        目前仅从订阅记录中移除，后续可扩展适配器级别的取消订阅。

        Args:
            exchange_name: 交易所标识
            stream_type: 数据流类型
            symbol: 交易对
            interval: K线周期
        """
        subscription_key = (exchange_name, stream_type, symbol, interval)
        self._subscriptions.discard(subscription_key)
        logger.info(
            f"数据流已取消订阅: {exchange_name} {stream_type} "
            f"{symbol} {interval or ''}"
        )

    def get_active_subscriptions(self) -> List[Dict[str, str]]:
        """
        获取当前所有活跃的订阅信息。

        Returns:
            订阅信息字典列表
        """
        return [
            {
                "exchange": sub[0],
                "stream_type": sub[1],
                "symbol": sub[2],
                "interval": sub[3],
            }
            for sub in self._subscriptions
        ]

    def _schedule_reconnect(self, exchange_name: str) -> None:
        """
        为指定交易所调度后台重连任务。
        使用指数退避策略，防止频繁重连对交易所API造成压力。

        Args:
            exchange_name: 需要重连的交易所标识
        """
        if not self._is_running:
            return

        # 同一交易所不重复创建重连任务
        if exchange_name in self._reconnect_tasks:
            existing_task = self._reconnect_tasks[exchange_name]
            if not existing_task.done():
                return

        task = asyncio.create_task(self._reconnect_loop(exchange_name))
        self._reconnect_tasks[exchange_name] = task

    async def _reconnect_loop(self, exchange_name: str) -> None:
        """
        重连循环，使用指数退避策略尝试恢复连接。

        重连成功后会自动恢复该交易所下所有之前的订阅。

        Args:
            exchange_name: 交易所标识
        """
        adapter = self._adapters.get(exchange_name)
        if not adapter:
            return

        current_delay = self._reconnect_delay_seconds
        attempt_count = 0

        while self._is_running:
            attempt_count += 1
            logger.warning(
                f"交易所 {exchange_name} 第 {attempt_count} 次重连尝试，"
                f"等待 {current_delay:.1f} 秒..."
            )

            await asyncio.sleep(current_delay)

            try:
                # 尝试先断开再重新连接，确保清理旧的连接状态
                try:
                    await adapter.disconnect()
                except Exception:
                    pass

                await adapter.connect()
                logger.info(f"交易所 {exchange_name} 重连成功（第 {attempt_count} 次尝试）")

                # 重连成功后恢复该交易所下的所有订阅
                await self._restore_subscriptions(exchange_name)

                # 重连成功，清理任务引用并退出循环
                self._reconnect_tasks.pop(exchange_name, None)
                return

            except Exception as reconnect_error:
                logger.error(
                    f"交易所 {exchange_name} 重连失败（第 {attempt_count} 次）: "
                    f"{reconnect_error}"
                )
                # 指数退避：每次失败后延迟翻倍，但不超过上限
                current_delay = min(
                    current_delay * 2, self._max_reconnect_delay_seconds
                )

    async def _restore_subscriptions(self, exchange_name: str) -> None:
        """
        恢复指定交易所下之前注册的所有订阅。
        重连后调用此方法，确保数据流不中断。

        注意：恢复订阅时的回调函数使用占位的日志回调，
        实际使用中应通过外部机制重新绑定真正的回调。

        Args:
            exchange_name: 交易所标识
        """
        # 筛选出该交易所的所有订阅记录
        exchange_subscriptions = [
            sub for sub in self._subscriptions if sub[0] == exchange_name
        ]

        for sub in exchange_subscriptions:
            _, stream_type, symbol, interval = sub
            try:
                logger.info(
                    f"恢复订阅: {exchange_name} {stream_type} "
                    f"{symbol} {interval or ''}"
                )
                # 占位回调：仅记录日志，实际业务中应替换为真正的数据处理回调
                placeholder_callback = lambda data, st=stream_type, sym=symbol: (
                    logger.debug(f"恢复订阅数据到达: {st} {sym}")
                )
                await self.subscribe(
                    exchange_name, stream_type, symbol,
                    placeholder_callback, interval
                )
            except Exception as restore_error:
                logger.error(
                    f"恢复订阅失败: {exchange_name} {stream_type} "
                    f"{symbol} - {restore_error}"
                )

"""
Redis连接管理模块。
提供Redis连接池和常用操作封装。
"""
import json
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings


class RedisManager:
    """
    Redis连接管理器，封装常用操作。
    支持JSON序列化存取、发布订阅和基本键操作。
    """

    def __init__(self):
        """初始化管理器，连接实例默认为空"""
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """
        建立Redis连接。
        使用连接池模式，最大50个连接，自动解码响应为字符串。
        """
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,  # 自动将字节解码为字符串
            max_connections=50,
        )

    async def disconnect(self):
        """断开Redis连接，释放连接池资源"""
        if self._redis:
            await self._redis.close()

    @property
    def client(self) -> aioredis.Redis:
        """
        获取Redis客户端实例。

        Raises:
            RuntimeError: 如果尚未调用connect()建立连接
        """
        if not self._redis:
            raise RuntimeError("Redis尚未连接，请先调用connect()")
        return self._redis

    async def set_json(self, key: str, value: Any, expire: int = 0):
        """
        以JSON格式存储数据。

        Args:
            key: Redis键名
            value: 待存储的数据，会自动序列化为JSON
            expire: 过期时间（秒），0表示不过期
        """
        data = json.dumps(value, ensure_ascii=False, default=str)
        if expire > 0:
            await self.client.setex(key, expire, data)
        else:
            await self.client.set(key, data)

    async def get_json(self, key: str) -> Optional[Any]:
        """
        读取JSON格式数据。

        Args:
            key: Redis键名

        Returns:
            反序列化后的Python对象，键不存在时返回None
        """
        data = await self.client.get(key)
        if data:
            return json.loads(data)
        return None

    async def publish(self, channel: str, message: Any):
        """
        向指定频道发布消息（Pub/Sub模式）。

        Args:
            channel: 频道名称
            message: 消息内容，会自动序列化为JSON
        """
        data = json.dumps(message, ensure_ascii=False, default=str)
        await self.client.publish(channel, data)

    async def delete(self, key: str):
        """
        删除指定键。

        Args:
            key: 要删除的Redis键名
        """
        await self.client.delete(key)

    async def exists(self, key: str) -> bool:
        """
        检查键是否存在。

        Args:
            key: Redis键名

        Returns:
            键存在返回True，否则返回False
        """
        return await self.client.exists(key) > 0


# 全局Redis管理器单例，应用启动时调用connect()初始化
redis_manager = RedisManager()

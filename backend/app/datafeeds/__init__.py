"""
数据源模块包。
统一管理交易所数据适配器、WebSocket连接和REST客户端。
"""
from app.datafeeds.base import BaseExchangeAdapter
from app.datafeeds.schemas import (
    UnifiedKline,
    UnifiedTrade,
    UnifiedOrderbook,
    UnifiedFunding,
    UnifiedOI,
)
from app.datafeeds.manager import DatafeedManager

__all__ = [
    "BaseExchangeAdapter",
    "UnifiedKline",
    "UnifiedTrade",
    "UnifiedOrderbook",
    "UnifiedFunding",
    "UnifiedOI",
    "DatafeedManager",
]

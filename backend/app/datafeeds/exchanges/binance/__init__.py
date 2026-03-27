"""
Binance 交易所适配器子包。
包含 REST 客户端、现货/合约 WebSocket、数据解析器和统一适配器。
"""
from app.datafeeds.exchanges.binance.adapter import BinanceAdapter

__all__ = ["BinanceAdapter"]

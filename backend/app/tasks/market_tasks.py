"""
行情数据定时任务模块。
定期从交易所获取和同步市场数据。
"""
from loguru import logger


async def fetch_klines_periodic(symbol: str = "BTCUSDT", interval: str = "1h"):
    """定期获取最新K线数据"""
    logger.info(f"定时任务: 获取K线 {symbol}/{interval}")
    # 实际使用时通过datafeeds模块获取数据并保存到数据库


async def sync_funding_rate(symbol: str = "BTCUSDT"):
    """同步资金费率"""
    logger.info(f"定时任务: 同步资金费率 {symbol}")


async def sync_open_interest(symbol: str = "BTCUSDT"):
    """同步持仓量"""
    logger.info(f"定时任务: 同步持仓量 {symbol}")


async def cleanup_old_trades(days: int = 7):
    """清理超期的逐笔成交数据"""
    logger.info(f"定时任务: 清理{days}天前的成交数据")

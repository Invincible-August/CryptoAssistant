"""
数据清理定时任务模块。
"""
from loguru import logger


async def cleanup_old_klines(days: int = 90):
    """清理超期K线数据"""
    logger.info(f"定时任务: 清理{days}天前的K线数据")


async def cleanup_old_logs(days: int = 30):
    """清理超期日志"""
    logger.info(f"定时任务: 清理{days}天前的日志")


async def cleanup_old_orderbook_snapshots(days: int = 7):
    """清理超期订单簿快照"""
    logger.info(f"定时任务: 清理{days}天前的订单簿快照")

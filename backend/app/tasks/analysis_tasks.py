"""
分析定时任务模块。
定期运行指标计算、因子计算和行为分析。
"""
from loguru import logger


async def run_periodic_analysis(symbol: str = "BTCUSDT"):
    """定期运行市场分析"""
    logger.info(f"定时任务: 运行市场分析 {symbol}")


async def compute_indicators_batch():
    """批量计算所有监控交易对的指标"""
    logger.info("定时任务: 批量计算指标")


async def compute_factors_batch():
    """批量计算所有监控交易对的因子"""
    logger.info("定时任务: 批量计算因子")

"""
AI相关定时任务模块。
"""
from loguru import logger


async def run_ai_analysis_periodic(symbol: str = "BTCUSDT"):
    """定期运行AI分析（仅在AI模块启用时生效）"""
    logger.info(f"定时任务: AI分析 {symbol}")


async def check_ai_artifact_expiry():
    """检查并清理过期的AI生成产物"""
    logger.info("定时任务: 检查AI产物过期状态")

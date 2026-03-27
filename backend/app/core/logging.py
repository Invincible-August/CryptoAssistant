"""
日志配置模块。
使用loguru提供统一的日志记录能力。
"""
import sys
from pathlib import Path
from loguru import logger
from app.core.config import settings


def setup_logging():
    """
    配置系统日志。
    同时输出到控制台和日志文件，支持日志轮转和自动压缩。
    """
    # 移除loguru默认的控制台处理器，避免重复输出
    logger.remove()

    # 添加控制台日志输出（带颜色高亮）
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )

    # 确保日志文件所在目录存在
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 添加文件日志输出（支持轮转、保留和压缩）
    logger.add(
        str(log_path),
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}:{function}:{line} | {message}",
        rotation="10 MB",       # 单个日志文件最大10MB，超过后自动轮转
        retention="30 days",    # 日志文件保留30天，过期自动删除
        compression="gz",       # 旧日志文件自动压缩为.gz格式节省磁盘空间
        encoding="utf-8",       # 使用UTF-8编码，确保中文日志正常写入
    )

    logger.info("日志系统初始化完成")

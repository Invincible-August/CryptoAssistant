"""
通用装饰器模块。
提供重试、限流、计时等实用装饰器。
"""
import asyncio
import time
import functools
from loguru import logger


def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    重试装饰器，支持指数退避。

    Args:
        max_retries: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避倍数
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"函数 {func.__name__} 第{attempt + 1}次执行失败: {e}，"
                            f"{current_delay:.1f}秒后重试..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            logger.error(f"函数 {func.__name__} 在{max_retries}次重试后仍然失败")
            raise last_exception

        return wrapper

    return decorator


def log_execution_time():
    """记录函数执行时间的装饰器"""

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            elapsed = time.time() - start
            logger.debug(f"{func.__name__} 执行耗时: {elapsed:.3f}秒")
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.debug(f"{func.__name__} 执行耗时: {elapsed:.3f}秒")
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator

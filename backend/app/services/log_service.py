"""
日志服务模块。
提供系统日志和错误日志的结构化写入与查询功能。

本模块将重要的业务事件和异常信息持久化到数据库的
system_logs 和 error_logs 表中，与 loguru 文件日志互补：
- loguru：写入日志文件，适合运维排查和实时监控
- 本服务：写入数据库，适合 Web 界面查询、统计分析和报警

两者协同工作，同一条日志会同时写入文件和数据库。
"""
import traceback as tb_module
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_log import SystemLog
from app.models.error_log import ErrorLog


# ==============================================================================
# 系统日志
# ==============================================================================

async def write_system_log(
    db: AsyncSession,
    level: str,
    module: str,
    message: str,
    detail: Optional[Dict[str, Any]] = None,
) -> SystemLog:
    """
    写入一条系统日志到数据库。

    同时通过 loguru 输出到文件和控制台，确保双通道记录。

    Args:
        db: 异步数据库会话
        level: 日志级别（DEBUG / INFO / WARNING / ERROR / CRITICAL）
        module: 产生日志的模块名称
        message: 日志消息正文
        detail: 附加详情数据（JSON 格式，可选）

    Returns:
        持久化后的 SystemLog 对象
    """
    # 创建数据库日志记录
    system_log = SystemLog(
        level=level.upper(),
        module=module,
        message=message,
        detail_json=detail,
    )

    db.add(system_log)
    await db.flush()

    # 同时通过 loguru 记录到文件
    log_text = f"[{module}] {message}"
    match level.upper():
        case "DEBUG":
            logger.debug(log_text)
        case "INFO":
            logger.info(log_text)
        case "WARNING":
            logger.warning(log_text)
        case "ERROR":
            logger.error(log_text)
        case "CRITICAL":
            logger.critical(log_text)
        case _:
            logger.info(log_text)

    return system_log


async def get_system_logs(
    db: AsyncSession,
    level: Optional[str] = None,
    module: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[List[SystemLog], int]:
    """
    分页查询系统日志，支持多维度过滤。

    Args:
        db: 异步数据库会话
        level: 按日志级别过滤（可选）
        module: 按模块名称过滤（可选）
        start_time: 开始时间（可选）
        end_time: 结束时间（可选）
        keyword: 按消息内容模糊搜索（可选）
        skip: 分页偏移量
        limit: 每页条数

    Returns:
        (日志列表, 总记录数) 的元组
    """
    # 构建查询条件
    conditions = []

    if level:
        conditions.append(SystemLog.level == level.upper())
    if module:
        conditions.append(SystemLog.module == module)
    if start_time:
        conditions.append(SystemLog.created_at >= start_time)
    if end_time:
        conditions.append(SystemLog.created_at <= end_time)
    if keyword:
        # 消息内容模糊搜索
        conditions.append(SystemLog.message.ilike(f"%{keyword}%"))

    # 数据查询
    query = select(SystemLog)
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(desc(SystemLog.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    logs = list(result.scalars().all())

    # 总数查询
    from sqlalchemy import func
    count_query = select(func.count(SystemLog.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    logger.debug(f"系统日志查询: 返回 {len(logs)} 条，总计 {total} 条")
    return logs, total


# ==============================================================================
# 错误日志
# ==============================================================================

async def write_error_log(
    db: AsyncSession,
    module: str,
    error_type: str,
    message: str,
    traceback_str: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ErrorLog:
    """
    写入一条错误日志到数据库。

    专门记录系统异常和错误，包含完整的堆栈回溯和上下文信息。
    如果未提供 traceback_str，会自动尝试捕获当前异常的堆栈。

    Args:
        db: 异步数据库会话
        module: 产生错误的模块名称
        error_type: 错误类型（如 "ConnectionError"、"ValueError"）
        message: 错误描述消息
        traceback_str: 完整堆栈回溯字符串（可选，None 时自动捕获）
        context: 触发错误时的上下文数据（可选，JSON 格式）

    Returns:
        持久化后的 ErrorLog 对象
    """
    # 如果未提供堆栈，尝试自动获取当前异常的堆栈
    if traceback_str is None:
        try:
            traceback_str = tb_module.format_exc()
            # 如果没有活跃异常，format_exc 返回 "NoneType: None\n"
            if "NoneType: None" in traceback_str:
                traceback_str = None
        except Exception:
            traceback_str = None

    error_log = ErrorLog(
        module=module,
        error_type=error_type,
        message=message,
        traceback=traceback_str,
        context_json=context,
    )

    db.add(error_log)
    await db.flush()

    # 同时通过 loguru 记录到文件
    logger.error(
        f"[{module}] {error_type}: {message}"
    )

    return error_log


async def get_error_logs(
    db: AsyncSession,
    module: Optional[str] = None,
    error_type: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[List[ErrorLog], int]:
    """
    分页查询错误日志，支持多维度过滤。

    Args:
        db: 异步数据库会话
        module: 按模块名称过滤（可选）
        error_type: 按错误类型过滤（可选）
        start_time: 开始时间（可选）
        end_time: 结束时间（可选）
        keyword: 按消息内容模糊搜索（可选）
        skip: 分页偏移量
        limit: 每页条数

    Returns:
        (错误日志列表, 总记录数) 的元组
    """
    conditions = []

    if module:
        conditions.append(ErrorLog.module == module)
    if error_type:
        conditions.append(ErrorLog.error_type == error_type)
    if start_time:
        conditions.append(ErrorLog.created_at >= start_time)
    if end_time:
        conditions.append(ErrorLog.created_at <= end_time)
    if keyword:
        conditions.append(ErrorLog.message.ilike(f"%{keyword}%"))

    # 数据查询
    query = select(ErrorLog)
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(desc(ErrorLog.created_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    logs = list(result.scalars().all())

    # 总数查询
    from sqlalchemy import func
    count_query = select(func.count(ErrorLog.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    logger.debug(f"错误日志查询: 返回 {len(logs)} 条，总计 {total} 条")
    return logs, total


async def write_exception(
    db: AsyncSession,
    module: str,
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
) -> ErrorLog:
    """
    便捷方法：直接从异常对象创建错误日志。

    自动提取异常类型名、消息和堆栈信息，简化调用方代码。

    Args:
        db: 异步数据库会话
        module: 模块名称
        exception: 捕获到的异常对象
        context: 上下文数据（可选）

    Returns:
        ErrorLog 对象
    """
    error_type = type(exception).__name__
    message = str(exception)

    # 提取异常的完整堆栈回溯
    try:
        traceback_str = "".join(
            tb_module.format_exception(type(exception), exception, exception.__traceback__)
        )
    except Exception:
        traceback_str = None

    return await write_error_log(
        db=db,
        module=module,
        error_type=error_type,
        message=message,
        traceback_str=traceback_str,
        context=context,
    )

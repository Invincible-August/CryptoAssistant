"""
系统日志API路由。
提供系统日志和错误日志的查询接口。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.system_log import SystemLog
from app.models.error_log import ErrorLog
from app.schemas.common import ResponseBase

router = APIRouter()


@router.get("/system", response_model=ResponseBase, summary="获取系统日志")
async def get_system_logs(
    level: str = Query(None, description="日志级别过滤"),
    module: str = Query(None, description="模块过滤"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取系统运行日志"""
    query = select(SystemLog).order_by(desc(SystemLog.created_at)).limit(limit)
    if level:
        query = query.where(SystemLog.level == level)
    if module:
        query = query.where(SystemLog.module == module)

    result = await db.execute(query)
    logs = result.scalars().all()

    data = [
        {
            "id": log.id,
            "level": log.level,
            "module": log.module,
            "message": log.message,
            "detail": log.detail_json,
            "created_at": str(log.created_at),
        }
        for log in logs
    ]
    return ResponseBase(data=data)


@router.get("/errors", response_model=ResponseBase, summary="获取错误日志")
async def get_error_logs(
    module: str = Query(None, description="模块过滤"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取系统错误日志"""
    query = select(ErrorLog).order_by(desc(ErrorLog.created_at)).limit(limit)
    if module:
        query = query.where(ErrorLog.module == module)

    result = await db.execute(query)
    logs = result.scalars().all()

    data = [
        {
            "id": log.id,
            "module": log.module,
            "error_type": log.error_type,
            "message": log.message,
            "traceback": log.traceback,
            "context": log.context_json,
            "created_at": str(log.created_at),
        }
        for log in logs
    ]
    return ResponseBase(data=data)

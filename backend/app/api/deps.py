"""
API依赖注入模块。
提供数据库会话、当前用户、权限检查等通用依赖。
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db_session
from app.core.security import decode_access_token
from app.models.user import User

# Bearer Token认证方案
security_scheme = HTTPBearer()


async def get_db(session: AsyncSession = Depends(get_db_session)):
    """获取数据库会话"""
    return session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户，验证JWT令牌"""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="令牌载荷无效")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已被禁用")

    return user


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user

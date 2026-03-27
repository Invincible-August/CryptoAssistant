"""
用户管理服务模块。
提供用户 CRUD 操作的业务逻辑封装。
所有方法接受 AsyncSession 作为参数，由调用方负责事务控制。
"""
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserUpdate


async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    """
    根据用户 ID 查询用户。

    Args:
        db: 异步数据库会话
        user_id: 用户主键 ID

    Returns:
        User 对象

    Raises:
        NotFoundError: 用户不存在
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"用户查询失败 - ID 不存在: {user_id}")
        raise NotFoundError(resource="用户", message=f"用户 ID={user_id} 不存在")

    return user


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    根据用户名查询用户。

    Args:
        db: 异步数据库会话
        username: 用户名

    Returns:
        User 对象，不存在时返回 None
    """
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> tuple[List[User], int]:
    """
    分页查询用户列表，支持按角色和状态过滤。

    Args:
        db: 异步数据库会话
        skip: 跳过的记录数（分页偏移量）
        limit: 每页返回的最大记录数
        role: 按角色过滤（可选），如 "admin" / "user"
        is_active: 按账户激活状态过滤（可选）

    Returns:
        (用户列表, 总记录数) 的元组
    """
    # 构建基础查询
    query = select(User)
    count_query = select(func.count(User.id))

    # 按角色过滤
    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    # 按激活状态过滤
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    # 按创建时间倒序排列，最新注册的在前
    query = query.order_by(User.created_at.desc())

    # 分页
    query = query.offset(skip).limit(limit)

    # 执行查询
    result = await db.execute(query)
    users = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total_count = count_result.scalar() or 0

    logger.debug(f"用户列表查询: 返回 {len(users)} 条，总计 {total_count} 条")
    return users, total_count


async def update_user(
    db: AsyncSession, user_id: int, update_data: UserUpdate
) -> User:
    """
    更新用户信息。

    仅更新 update_data 中非 None 的字段，实现部分更新。

    Args:
        db: 异步数据库会话
        user_id: 待更新的用户 ID
        update_data: 更新数据（email / role / is_active）

    Returns:
        更新后的 User 对象

    Raises:
        NotFoundError: 用户不存在
    """
    # 先查询目标用户
    user = await get_user_by_id(db, user_id)

    # 逐字段更新，仅处理非 None 值
    if update_data.email is not None:
        user.email = update_data.email
        logger.debug(f"用户 ID={user_id} 邮箱更新为: {update_data.email}")

    if update_data.role is not None:
        user.role = update_data.role
        logger.debug(f"用户 ID={user_id} 角色更新为: {update_data.role}")

    if update_data.is_active is not None:
        user.is_active = update_data.is_active
        logger.debug(f"用户 ID={user_id} 激活状态更新为: {update_data.is_active}")

    # flush 将变更写入数据库缓冲区，但不提交事务
    await db.flush()

    logger.info(f"用户信息已更新: ID={user_id}, username={user.username}")
    return user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """
    删除指定用户。

    执行物理删除，从数据库中永久移除用户记录。
    如果需要软删除，建议使用 update_user 将 is_active 设为 False。

    Args:
        db: 异步数据库会话
        user_id: 待删除的用户 ID

    Returns:
        删除成功返回 True

    Raises:
        NotFoundError: 用户不存在
    """
    user = await get_user_by_id(db, user_id)

    await db.delete(user)
    await db.flush()

    logger.info(f"用户已删除: ID={user_id}, username={user.username}")
    return True


async def change_password(
    db: AsyncSession, user_id: int, new_password: str
) -> User:
    """
    修改用户密码。

    Args:
        db: 异步数据库会话
        user_id: 用户 ID
        new_password: 新的明文密码

    Returns:
        更新后的 User 对象

    Raises:
        NotFoundError: 用户不存在
        ValidationError: 新密码长度不满足要求
    """
    if len(new_password) < 6:
        raise ValidationError(message="密码长度不能少于6个字符")

    user = await get_user_by_id(db, user_id)
    user.password_hash = hash_password(new_password)
    await db.flush()

    logger.info(f"用户密码已更新: ID={user_id}, username={user.username}")
    return user

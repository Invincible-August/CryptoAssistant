"""
认证服务模块。
提供用户登录认证、注册创建和令牌解析等核心认证业务逻辑。
所有数据库操作通过外部注入的 AsyncSession 完成，保持服务层的可测试性。
"""
from typing import Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ValidationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import UserCreate


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[User]:
    """
    验证用户凭据，认证通过返回用户对象。

    认证流程：
    1. 根据用户名查询数据库获取用户记录
    2. 验证密码哈希是否匹配
    3. 检查账户是否处于激活状态

    Args:
        db: 异步数据库会话
        username: 用户提交的用户名
        password: 用户提交的明文密码

    Returns:
        认证通过返回 User 对象，失败返回 None

    Raises:
        AuthenticationError: 用户不存在、密码错误或账户已禁用
    """
    try:
        # 根据用户名查询用户记录
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning(f"登录失败 - 用户不存在: {username}")
            raise AuthenticationError(message="用户名或密码错误")

        # 校验密码哈希
        if not verify_password(password, user.password_hash):
            logger.warning(f"登录失败 - 密码错误: {username}")
            raise AuthenticationError(message="用户名或密码错误")

        # 检查账户激活状态
        if not user.is_active:
            logger.warning(f"登录失败 - 账户已禁用: {username}")
            raise AuthenticationError(message="账户已被禁用，请联系管理员")

        logger.info(f"用户认证成功: {username} (ID={user.id})")
        return user

    except AuthenticationError:
        raise
    except Exception as auth_error:
        logger.error(f"认证过程发生异常: {auth_error}", exc_info=True)
        raise AuthenticationError(message="认证过程发生内部错误")


async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    """
    创建新用户并持久化到数据库。

    流程：
    1. 检查用户名是否已被占用
    2. 对密码进行哈希处理
    3. 创建 User ORM 实例并写入数据库

    Args:
        db: 异步数据库会话
        user_data: 用户注册数据（包含用户名、密码、邮箱等）

    Returns:
        新创建的 User 对象

    Raises:
        ValidationError: 用户名已存在
    """
    try:
        # 检查用户名唯一性
        stmt = select(User).where(User.username == user_data.username)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.warning(f"注册失败 - 用户名已存在: {user_data.username}")
            raise ValidationError(
                message=f"用户名 '{user_data.username}' 已被注册"
            )

        # 创建新用户，密码存储为哈希值
        new_user = User(
            username=user_data.username,
            password_hash=hash_password(user_data.password),
            email=user_data.email,
            role=user_data.role,
        )

        db.add(new_user)
        await db.flush()  # 刷入数据库获取自增ID，但不提交事务

        logger.info(
            f"新用户创建成功: {new_user.username} "
            f"(ID={new_user.id}, 角色={new_user.role})"
        )
        return new_user

    except ValidationError:
        raise
    except Exception as create_error:
        logger.error(f"创建用户失败: {create_error}", exc_info=True)
        raise ValidationError(message="创建用户时发生内部错误")


async def get_current_user(db: AsyncSession, token: str) -> User:
    """
    根据 JWT 令牌解析当前登录用户。

    流程：
    1. 解码 JWT 令牌，提取用户 ID
    2. 根据 ID 查询数据库获取完整用户信息
    3. 校验用户状态

    Args:
        db: 异步数据库会话
        token: JWT 访问令牌字符串

    Returns:
        当前登录的 User 对象

    Raises:
        AuthenticationError: 令牌无效/过期或对应用户不存在
    """
    # 解码令牌
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("令牌解析失败 - 令牌无效或已过期")
        raise AuthenticationError(message="令牌无效或已过期，请重新登录")

    # 从载荷中提取用户 ID（存储在 "sub" 字段中）
    user_id = payload.get("sub")
    if user_id is None:
        logger.warning("令牌载荷缺少用户ID (sub)")
        raise AuthenticationError(message="令牌格式异常")

    try:
        # 根据 ID 查询用户
        stmt = select(User).where(User.id == int(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            logger.warning(f"令牌对应的用户不存在: ID={user_id}")
            raise AuthenticationError(message="用户不存在")

        if not user.is_active:
            logger.warning(f"令牌对应的用户已禁用: {user.username}")
            raise AuthenticationError(message="账户已被禁用")

        return user

    except AuthenticationError:
        raise
    except Exception as query_error:
        logger.error(
            f"根据令牌查询用户失败: {query_error}", exc_info=True
        )
        raise AuthenticationError(message="用户验证过程发生内部错误")


def generate_access_token(user: User) -> str:
    """
    为已认证用户生成 JWT 访问令牌。

    令牌载荷包含用户 ID 和角色信息。

    Args:
        user: 已通过认证的用户对象

    Returns:
        编码后的 JWT 令牌字符串
    """
    token_data = {
        "sub": str(user.id),
        "role": user.role,
    }
    access_token = create_access_token(data=token_data)
    logger.debug(f"为用户 {user.username} 生成访问令牌")
    return access_token

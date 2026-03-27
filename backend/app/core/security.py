"""
安全认证模块。
提供密码哈希、JWT令牌生成与验证功能。

密码哈希直接使用 ``bcrypt`` 库，避免 ``passlib`` 与 ``bcrypt`` 4.x 的
``__about__`` 版本探测不兼容问题；存库格式仍为标准 bcrypt 字符串，可与
历史 passlib 生成的哈希互验。
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
from jose import jwt, JWTError
from app.core.config import settings

# JWT签名算法，HS256为对称加密，适合单体应用
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """
    对明文密码进行 bcrypt 哈希处理。

    Args:
        password: 用户输入的明文密码

    Returns:
        bcrypt 哈希后的密码字符串（UTF-8 可解码的 ASCII 形式）
    """
    salt = bcrypt.gensalt()
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与数据库中存储的 bcrypt 哈希是否匹配。

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码

    Returns:
        匹配返回 True；格式非法或校验失败返回 False
    """
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌。

    Args:
        data: 令牌载荷数据，通常包含用户ID和角色信息
        expires_delta: 自定义过期时间，默认使用配置文件中的值

    Returns:
        编码后的JWT字符串
    """
    # 复制载荷数据，避免修改原始字典
    to_encode = data.copy()

    # 计算令牌过期时间
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # 将过期时间写入载荷
    to_encode.update({"exp": expire})

    # 使用密钥和算法对载荷进行签名编码
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码JWT访问令牌。

    Args:
        token: 待解码的JWT字符串

    Returns:
        解码成功返回载荷字典，失败（过期、篡改等）返回None
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        # JWT解码失败：可能是令牌过期、签名无效或格式错误
        return None

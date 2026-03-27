"""
认证鉴权相关数据模型

包含登录请求/响应、JWT Token 载荷等结构，
用于用户登录认证和 Token 校验流程。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """
    登录请求模型

    用户通过用户名和密码进行身份认证。

    Attributes:
        username: 用户名，长度 3~50 个字符
        password: 密码，长度 6~128 个字符
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="用户名",
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="用户密码",
    )


class LoginResponse(BaseModel):
    """
    登录成功响应模型

    认证通过后返回 JWT 访问令牌。

    Attributes:
        access_token: JWT 访问令牌字符串
        token_type: 令牌类型，固定为 "bearer"
    """

    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class TokenPayload(BaseModel):
    """
    JWT Token 载荷模型

    解析 JWT 后得到的结构化载荷数据，用于鉴权中间件。

    Attributes:
        sub: 用户唯一标识（user_id）
        role: 用户角色，如 "admin"、"user"
        exp: Token 过期时间戳
    """

    sub: int = Field(..., description="用户ID（subject）")
    role: str = Field(default="user", description="用户角色")
    exp: Optional[datetime] = Field(default=None, description="Token 过期时间")

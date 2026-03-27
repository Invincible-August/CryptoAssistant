"""
用户管理相关数据模型

包含用户创建、更新、查询响应等结构，
用于用户 CRUD 操作的请求和响应序列化。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import ResponseList


class UserCreate(BaseModel):
    """
    创建用户请求模型

    注册新用户时提交的数据结构。

    Attributes:
        username: 用户名，3~50 个字符，需唯一
        password: 密码，6~128 个字符
        email: 可选的电子邮箱地址
        role: 用户角色，默认为普通用户 "user"
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="用户名，需唯一",
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="用户密码",
    )
    email: Optional[EmailStr] = Field(default=None, description="电子邮箱")
    role: str = Field(default="user", description="用户角色，默认 user")


class UserUpdate(BaseModel):
    """
    更新用户请求模型

    部分更新用户信息，所有字段均为可选。

    Attributes:
        email: 新的电子邮箱地址
        role: 新的用户角色
        is_active: 是否启用账户
    """

    email: Optional[EmailStr] = Field(default=None, description="电子邮箱")
    role: Optional[str] = Field(default=None, description="用户角色")
    is_active: Optional[bool] = Field(default=None, description="账户是否启用")


class UserResponse(BaseModel):
    """
    用户信息响应模型

    从数据库 ORM 对象转换而来，返回给前端的用户详情。

    Attributes:
        id: 用户主键 ID
        username: 用户名
        email: 电子邮箱
        role: 用户角色
        is_active: 账户是否启用
        created_at: 账户创建时间
    """

    # 开启 from_attributes 以支持从 ORM 模型直接转换
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: Optional[str] = Field(default=None, description="电子邮箱")
    role: str = Field(..., description="用户角色")
    is_active: bool = Field(default=True, description="是否启用")
    created_at: datetime = Field(..., description="创建时间")


# 用户列表分页响应，复用通用分页模型
UserListResponse = ResponseList[UserResponse]

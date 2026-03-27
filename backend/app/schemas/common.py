"""
通用响应模型模块

定义统一的 API 响应格式、分页参数等公共数据结构，
供所有业务模块复用。
"""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

# 泛型类型变量，用于分页列表响应中的数据项类型
T = TypeVar("T")


class ResponseBase(BaseModel):
    """
    统一 API 响应基类

    所有接口返回值都应遵循此结构，保证前端解析一致性。

    Attributes:
        code: 业务状态码，200 表示成功
        message: 响应描述信息
        data: 响应数据载荷，类型不固定
    """

    code: int = Field(default=200, description="业务状态码，200 表示成功")
    message: str = Field(default="success", description="响应描述信息")
    data: Any = Field(default=None, description="响应数据载荷")


class ResponseList(BaseModel, Generic[T]):
    """
    分页列表响应模型

    用于需要分页展示的列表接口，携带总数和分页元信息。

    Attributes:
        code: 业务状态码
        message: 响应描述信息
        data: 当前页数据列表
        total: 满足条件的数据总条数
        page: 当前页码（从 1 开始）
        page_size: 每页数据条数
    """

    code: int = Field(default=200, description="业务状态码")
    message: str = Field(default="success", description="响应描述信息")
    data: List[T] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(default=0, description="数据总条数")
    page: int = Field(default=1, ge=1, description="当前页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


class PageParams(BaseModel):
    """
    分页查询参数

    前端在请求列表接口时传入此参数来控制分页。

    Attributes:
        page: 请求的页码，最小为 1
        page_size: 每页返回条数，范围 1~100
    """

    page: int = Field(default=1, ge=1, description="请求页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")

"""
系统配置相关数据模型

定义模块配置的更新/查询以及系统全局配置响应等结构，
用于动态管理各业务模块的启停和参数调整。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ModuleConfigUpdate(BaseModel):
    """
    模块配置更新请求模型

    更新某个业务模块的启用状态或配置参数。

    Attributes:
        module_name: 模块名称（如 monitor, analysis, execution）
        enabled: 是否启用该模块
        config_json: 模块配置参数 JSON
    """

    module_name: str = Field(..., description="模块名称")
    enabled: bool = Field(default=True, description="是否启用")
    config_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="模块配置参数",
    )


class ModuleConfigResponse(BaseModel):
    """
    模块配置响应模型

    从数据库读取的完整模块配置记录。

    Attributes:
        id: 配置记录主键
        module_name: 模块名称
        enabled: 是否启用
        config_json: 配置参数
        updated_at: 最后更新时间
    """

    # 支持从 ORM 对象直接转换
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="配置ID")
    module_name: str = Field(..., description="模块名称")
    enabled: bool = Field(default=True, description="是否启用")
    config_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="配置参数",
    )
    updated_at: datetime = Field(..., description="最后更新时间")


class SystemConfigResponse(BaseModel):
    """
    系统全局配置响应模型

    聚合所有模块配置和交易所连接配置，用于系统管理面板展示。

    Attributes:
        modules: 所有业务模块的配置列表
        exchange_configs: 交易所连接配置列表（脱敏后）
    """

    modules: List[ModuleConfigResponse] = Field(
        default_factory=list,
        description="业务模块配置列表",
    )
    exchange_configs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="交易所连接配置（脱敏）",
    )

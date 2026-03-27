"""
量化因子相关数据模型

定义因子元数据、计算请求和计算结果等结构，
用于多因子评分体系的注册、计算和展示。
"""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class FactorMeta(BaseModel):
    """
    量化因子元信息模型

    描述一个因子的完整元数据，包括参数定义、输出格式和评分权重。
    由因子注册中心统一管理，供多因子综合评分引擎使用。

    Attributes:
        factor_key: 因子唯一标识（如 momentum_score, volatility_rank）
        name: 因子显示名称
        description: 因子功能描述
        source: 来源模块或作者
        version: 因子版本号
        category: 因子分类（momentum / value / volatility / sentiment）
        params_schema: 参数 JSON Schema
        output_schema: 输出 JSON Schema
        display_config: 前端展示配置
        score_weight: 在综合评分中的默认权重（0.0 ~ 1.0）
    """

    model_config = ConfigDict(from_attributes=True)

    factor_key: str = Field(..., description="因子唯一标识")
    name: str = Field(..., description="因子显示名称")
    description: str = Field(default="", description="因子功能描述")
    source: str = Field(default="system", description="来源模块或作者")
    version: str = Field(default="1.0.0", description="版本号")
    category: str = Field(
        default="custom",
        description="分类：momentum / value / volatility / sentiment / custom",
    )
    params_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="参数 JSON Schema",
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="输出 JSON Schema",
    )
    display_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="前端展示配置",
    )
    score_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="综合评分默认权重",
    )


class FactorCalcRequest(BaseModel):
    """
    因子计算请求模型

    前端或策略引擎请求计算某个因子时提交的参数。

    Attributes:
        factor_key: 要计算的因子标识
        symbol: 交易对
        exchange: 交易所名称
        market_type: 市场类型
        timeframe: 时间周期
        params: 因子计算参数
    """

    factor_key: str = Field(..., description="因子标识")
    symbol: str = Field(..., description="交易对")
    exchange: str = Field(default="binance", description="交易所名称")
    market_type: str = Field(default="spot", description="市场类型")
    timeframe: str = Field(default="1h", description="时间周期")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="计算参数",
    )


class FactorCalcResponse(BaseModel):
    """
    因子计算结果响应模型

    返回单个因子的计算得分和明细信息。

    Attributes:
        factor_key: 因子标识
        name: 因子名称
        source: 计算来源
        score: 因子得分（归一化后，通常 0~100）
        detail: 计算明细，包含中间数据和解释说明
    """

    factor_key: str = Field(..., description="因子标识")
    name: str = Field(..., description="因子名称")
    source: str = Field(default="system", description="计算来源")
    score: float = Field(..., description="因子得分")
    detail: Dict[str, Any] = Field(
        default_factory=dict,
        description="计算明细",
    )

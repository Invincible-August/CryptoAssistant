"""
行为分析相关数据模型

定义主力行为画像、分析请求和分析结果等结构，
用于庄家/主力行为识别与多维度市场分析。
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BehaviorProfile(BaseModel):
    """
    主力行为画像模型

    基于成交量、持仓量、资金流等多维数据综合刻画主力当前行为阶段，
    给出各维度评分和推演假设。

    Attributes:
        stage: 当前行为阶段（如 accumulation / markup / distribution / markdown）
        estimated_cost_zone: 估算主力成本区间，如 {"low": 60000, "high": 62000}
        control_strength_score: 控盘强度评分（0~100）
        capital_reserve_score: 资金储备评分（0~100）
        follow_score: 跟风盘强度评分（0~100）
        distribution_risk_score: 派发风险评分（0~100）
        fake_move_risk_score: 假突破/假跌风险评分（0~100）
        hypotheses: 行为假设列表，如 ["主力正在低位吸筹"]
        evidence: 支撑假设的证据列表
        risks: 当前阶段面临的主要风险
    """

    stage: str = Field(
        ...,
        description="行为阶段：accumulation / markup / distribution / markdown",
    )
    estimated_cost_zone: Dict[str, float] = Field(
        default_factory=dict,
        description="主力成本区间估算，如 {\"low\": 60000, \"high\": 62000}",
    )
    control_strength_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="控盘强度评分",
    )
    capital_reserve_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="资金储备评分",
    )
    follow_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="跟风盘强度评分",
    )
    distribution_risk_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="派发风险评分",
    )
    fake_move_risk_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="假突破/假跌风险评分",
    )
    hypotheses: List[str] = Field(
        default_factory=list,
        description="行为假设列表",
    )
    evidence: List[str] = Field(
        default_factory=list,
        description="支撑证据列表",
    )
    risks: List[str] = Field(
        default_factory=list,
        description="当前风险列表",
    )


class AnalysisRequest(BaseModel):
    """
    分析请求模型

    请求对指定交易对进行行为分析时提交的参数。

    Attributes:
        symbol: 交易对（如 BTCUSDT）
        exchange: 交易所名称
        market_type: 市场类型
        timeframe: 分析时间周期，可选
    """

    symbol: str = Field(..., description="交易对")
    exchange: str = Field(default="binance", description="交易所名称")
    market_type: str = Field(default="spot", description="市场类型")
    timeframe: Optional[str] = Field(default=None, description="分析时间周期")


class AnalysisResponse(BaseModel):
    """
    分析结果响应模型

    返回完整的行为分析报告，包含行为画像和文字总结。

    Attributes:
        symbol: 交易对
        exchange: 交易所名称
        market_type: 市场类型
        event_time: 分析时间
        behavior_profile: 主力行为画像
        summary: 分析总结（自然语言描述）
    """

    symbol: str = Field(..., description="交易对")
    exchange: str = Field(..., description="交易所名称")
    market_type: str = Field(..., description="市场类型")
    event_time: datetime = Field(..., description="分析时间")
    behavior_profile: BehaviorProfile = Field(..., description="行为画像")
    summary: str = Field(default="", description="分析总结")

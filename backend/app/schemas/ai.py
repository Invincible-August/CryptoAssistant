"""
AI 分析相关数据模型

定义 AI 分析请求/响应、反馈收集和制品提案等结构，
用于大模型驱动的智能分析和自动化制品生成流程。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AIAnalysisRequest(BaseModel):
    """
    AI 分析请求模型

    向 AI 分析引擎提交分析任务时使用的参数结构。

    Attributes:
        symbol: 交易对（如 BTCUSDT）
        exchange: 交易所名称
        market_type: 市场类型
        timeframe: 分析时间周期，可选
        custom_prompt: 自定义提示词，用于定制化分析需求
    """

    symbol: str = Field(..., description="交易对")
    exchange: str = Field(default="binance", description="交易所名称")
    market_type: str = Field(default="spot", description="市场类型")
    timeframe: Optional[str] = Field(default=None, description="分析时间周期")
    custom_prompt: Optional[str] = Field(
        default=None,
        description="自定义提示词，用于定制化分析",
    )


class AIAnalysisResponse(BaseModel):
    """
    AI 分析结果响应模型

    大模型返回的分析结果，包含文本分析和结构化数据。

    Attributes:
        symbol: 交易对
        analysis_text: AI 生成的分析文本（Markdown 格式）
        structured_result: 结构化分析结果（评分、标签等）
        direction_suggestion: 方向建议（long / short / neutral）
        risk_warnings: AI 识别的风险警告列表
        model_name: 使用的模型名称（如 gpt-4, claude-3）
        source: 数据来源标记，固定为 "ai"
    """

    symbol: str = Field(..., description="交易对")
    analysis_text: str = Field(default="", description="分析文本（Markdown）")
    structured_result: Dict[str, Any] = Field(
        default_factory=dict,
        description="结构化分析结果",
    )
    direction_suggestion: Optional[str] = Field(
        default=None,
        description="方向建议：long / short / neutral",
    )
    risk_warnings: List[str] = Field(
        default_factory=list,
        description="风险警告列表",
    )
    model_name: str = Field(default="", description="使用的模型名称")
    source: str = Field(default="ai", description="来源标记")


class AIFeedbackRequest(BaseModel):
    """
    AI 分析反馈请求模型

    用户对 AI 分析结果的反馈，用于持续优化模型效果。

    Attributes:
        record_id: 关联的分析记录 ID
        feedback_type: 反馈类型（positive / negative / correction）
        feedback_text: 反馈详细描述
    """

    record_id: int = Field(..., description="分析记录ID")
    feedback_type: str = Field(
        ...,
        description="反馈类型：positive / negative / correction",
    )
    feedback_text: str = Field(default="", description="反馈详情")


class AIArtifactProposal(BaseModel):
    """
    AI 制品提案模型

    AI 自动生成的指标/因子/策略等制品的提案结构，
    需经人工审核后方可正式启用。

    Attributes:
        artifact_type: 制品类型（indicator / factor / strategy）
        artifact_key: 制品唯一标识
        proposal_json: 提案内容（完整的制品定义 JSON）
    """

    artifact_type: str = Field(
        ...,
        description="制品类型：indicator / factor / strategy",
    )
    artifact_key: str = Field(..., description="制品唯一标识")
    proposal_json: Dict[str, Any] = Field(
        ...,
        description="提案内容 JSON",
    )


class AIArtifactResponse(BaseModel):
    """
    AI 制品响应模型

    制品提案的完整记录，包含审核状态和来源信息。

    Attributes:
        id: 制品记录主键
        artifact_type: 制品类型
        artifact_key: 制品唯一标识
        source: 来源（ai / user / system）
        proposal_json: 提案内容
        review_status: 审核状态（pending / approved / rejected）
        created_at: 创建时间
    """

    # 支持从 ORM 对象直接转换
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="记录ID")
    artifact_type: str = Field(..., description="制品类型")
    artifact_key: str = Field(..., description="制品标识")
    source: str = Field(default="ai", description="来源")
    proposal_json: Dict[str, Any] = Field(..., description="提案内容")
    review_status: str = Field(default="pending", description="审核状态")
    created_at: datetime = Field(..., description="创建时间")

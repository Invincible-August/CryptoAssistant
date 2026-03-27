"""
交易信号相关数据模型

定义止盈策略、信号推荐和信号响应等结构，
用于交易信号的生成、推送和展示。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TakeProfit(BaseModel):
    """
    止盈目标模型

    单个止盈点位的定义，支持分批止盈策略。

    Attributes:
        price: 止盈价格
        ratio: 该目标止盈比例（0.0~1.0），表示在此点位平掉多少仓位
        label: 标签说明，如 "TP1 - 保守目标"
    """

    price: float = Field(..., description="止盈价格")
    ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="止盈比例（0.0~1.0）",
    )
    label: str = Field(default="", description="止盈标签说明")


class SignalRecommendation(BaseModel):
    """
    交易信号推荐模型

    包含方向、置信度、入场区间、止损止盈等完整交易建议。

    Attributes:
        direction: 方向（long / short / neutral）
        confidence: 置信度（0.0~1.0）
        win_rate: 历史胜率参考
        entry_zone: 入场价格区间，如 {"low": 60000, "high": 60500}
        stop_loss: 止损价格
        take_profits: 多目标止盈列表
        tp_strategy: 止盈执行策略配置，如 {"type": "trailing", "callback_rate": 0.01}
        risks: 风险提示列表
        reasons: 推荐理由列表
        summary: 信号摘要文字
    """

    direction: str = Field(
        ...,
        description="方向：long / short / neutral",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="置信度",
    )
    win_rate: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="历史胜率参考",
    )
    entry_zone: Dict[str, float] = Field(
        default_factory=dict,
        description="入场区间，如 {\"low\": 60000, \"high\": 60500}",
    )
    stop_loss: float = Field(..., description="止损价格")
    take_profits: List[TakeProfit] = Field(
        default_factory=list,
        description="止盈目标列表",
    )
    tp_strategy: Dict[str, Any] = Field(
        default_factory=dict,
        description="止盈策略配置",
    )
    risks: List[str] = Field(
        default_factory=list,
        description="风险提示",
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="推荐理由",
    )
    summary: str = Field(default="", description="信号摘要")


class SignalResponse(BaseModel):
    """
    信号响应模型

    完整的交易信号输出，关联分析快照并附带推荐详情。

    Attributes:
        analysis_snapshot_id: 关联的分析快照 ID
        symbol: 交易对
        exchange: 交易所名称
        recommendation: 信号推荐详情
        created_at: 信号生成时间
    """

    analysis_snapshot_id: Optional[int] = Field(
        default=None,
        description="关联分析快照ID",
    )
    symbol: str = Field(..., description="交易对")
    exchange: str = Field(..., description="交易所名称")
    recommendation: SignalRecommendation = Field(..., description="信号推荐详情")
    created_at: datetime = Field(..., description="生成时间")

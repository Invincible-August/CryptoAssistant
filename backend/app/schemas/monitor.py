"""
监控管理相关数据模型

定义交易对监控配置的增删改查结构以及 WebSocket 实时状态模型，
用于监控任务的生命周期管理和运行状态展示。
"""

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SymbolWatchCreate(BaseModel):
    """
    创建监控任务请求模型

    指定交易所、交易对、市场类型和事件类型来创建新的监控订阅。

    Attributes:
        exchange: 交易所名称（如 binance）
        symbol: 交易对（如 BTCUSDT）
        market_type: 市场类型（spot / futures）
        event_type: 事件类型（如 kline, trade, depth, funding）
        config_json: 可选的自定义配置，如 K 线周期等
    """

    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    market_type: str = Field(..., description="市场类型：spot / futures")
    event_type: str = Field(..., description="事件类型：kline / trade / depth / funding")
    config_json: Optional[Dict] = Field(
        default=None,
        description="自定义配置，如 {\"interval\": \"1m\"}",
    )


class SymbolWatchUpdate(BaseModel):
    """
    更新监控任务请求模型

    部分更新监控任务的状态或配置信息。

    Attributes:
        watch_status: 监控状态（active / paused / stopped）
        config_json: 自定义配置
    """

    watch_status: Optional[str] = Field(
        default=None,
        description="监控状态：active / paused / stopped",
    )
    config_json: Optional[Dict] = Field(
        default=None,
        description="自定义配置",
    )


class SymbolWatchResponse(BaseModel):
    """
    监控任务响应模型

    从数据库读取的完整监控任务信息，包含所有配置字段和时间戳。

    Attributes:
        id: 监控任务主键
        exchange: 交易所名称
        symbol: 交易对
        market_type: 市场类型
        event_type: 事件类型
        watch_status: 监控状态
        config_json: 自定义配置
        created_at: 创建时间
    """

    # 支持从 ORM 对象直接转换
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="监控任务ID")
    exchange: str = Field(..., description="交易所名称")
    symbol: str = Field(..., description="交易对")
    market_type: str = Field(..., description="市场类型")
    event_type: str = Field(..., description="事件类型")
    watch_status: str = Field(default="active", description="监控状态")
    config_json: Optional[Dict] = Field(default=None, description="自定义配置")
    created_at: datetime = Field(..., description="创建时间")


class RealtimeStatus(BaseModel):
    """
    实时监控运行状态模型

    反映某个交易对的 WebSocket 连接情况和数据接收统计，
    用于前端监控面板展示。

    Attributes:
        symbol: 交易对
        market_type: 市场类型
        ws_connected: WebSocket 是否已连接
        last_update_time: 最后收到数据的时间
        data_counts: 各事件类型已接收的数据条数统计
    """

    symbol: str = Field(..., description="交易对")
    market_type: str = Field(..., description="市场类型")
    ws_connected: bool = Field(default=False, description="WS 是否连接")
    last_update_time: Optional[datetime] = Field(
        default=None,
        description="最后数据更新时间",
    )
    data_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="各事件类型数据计数，如 {\"kline\": 1200, \"trade\": 5600}",
    )

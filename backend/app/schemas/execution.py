"""
订单执行相关数据模型

定义下单请求、订单响应和成交明细等结构，
用于模拟/实盘交易的订单全生命周期管理。
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class OrderRequest(BaseModel):
    """
    下单请求模型

    提交交易订单时使用的参数结构。支持模拟盘和实盘两种模式。

    Attributes:
        symbol: 交易对（如 BTCUSDT）
        exchange: 交易所名称
        market_type: 市场类型（spot / futures）
        side: 交易方向（buy / sell）
        order_type: 订单类型（limit / market / stop_limit）
        price: 委托价格，市价单可为空
        quantity: 委托数量
        is_simulated: 是否为模拟订单，默认 True（安全第一）
        strategy_json: 关联的策略信息，便于回溯
    """

    symbol: str = Field(..., description="交易对")
    exchange: str = Field(default="binance", description="交易所名称")
    market_type: str = Field(default="spot", description="市场类型")
    side: str = Field(..., description="方向：buy / sell")
    order_type: str = Field(
        default="limit",
        description="类型：limit / market / stop_limit",
    )
    price: Optional[Decimal] = Field(
        default=None,
        description="委托价格，市价单可为空",
    )
    quantity: Decimal = Field(..., gt=0, description="委托数量")
    # 安全优先：默认走模拟盘，避免误操作真金白银
    is_simulated: bool = Field(
        default=True,
        description="是否模拟订单，默认 True",
    )
    strategy_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="关联策略信息",
    )


class OrderResponse(BaseModel):
    """
    订单响应模型

    订单提交后返回的完整订单信息。

    Attributes:
        id: 系统内部订单 ID
        symbol: 交易对
        side: 交易方向
        order_type: 订单类型
        price: 委托价格
        quantity: 委托数量
        status: 订单状态（pending / filled / partially_filled / cancelled / rejected）
        client_order_id: 客户端自定义订单 ID
        exchange_order_id: 交易所返回的订单 ID
        is_simulated: 是否为模拟订单
        created_at: 下单时间
    """

    # 支持从 ORM 对象直接转换
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="系统订单ID")
    symbol: str = Field(..., description="交易对")
    side: str = Field(..., description="方向")
    order_type: str = Field(..., description="订单类型")
    price: Optional[Decimal] = Field(default=None, description="委托价格")
    quantity: Decimal = Field(..., description="委托数量")
    status: str = Field(
        default="pending",
        description="状态：pending / filled / partially_filled / cancelled / rejected",
    )
    client_order_id: Optional[str] = Field(
        default=None,
        description="客户端订单ID",
    )
    exchange_order_id: Optional[str] = Field(
        default=None,
        description="交易所订单ID",
    )
    is_simulated: bool = Field(default=True, description="是否模拟订单")
    created_at: datetime = Field(..., description="下单时间")


class OrderFillResponse(BaseModel):
    """
    订单成交明细响应模型

    单笔成交的详细信息，一个订单可能对应多笔成交。

    Attributes:
        id: 成交记录主键
        order_id: 关联的订单 ID
        fill_price: 成交价格
        fill_quantity: 成交数量
        fee: 手续费
        fill_time: 成交时间
    """

    # 支持从 ORM 对象直接转换
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="成交记录ID")
    order_id: int = Field(..., description="关联订单ID")
    fill_price: Decimal = Field(..., description="成交价格")
    fill_quantity: Decimal = Field(..., description="成交数量")
    fee: Decimal = Field(default=Decimal("0"), description="手续费")
    fill_time: datetime = Field(..., description="成交时间")

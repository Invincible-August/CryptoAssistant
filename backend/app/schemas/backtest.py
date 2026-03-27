"""
回测系统相关数据模型

定义回测请求、成交记录、回测结果和回测响应等结构，
用于策略回测任务的提交、执行和结果展示。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BacktestRequest(BaseModel):
    """
    回测任务请求模型

    提交一个新的策略回测任务时使用的参数结构。

    Attributes:
        name: 回测任务名称（便于区分和检索）
        symbol: 交易对
        exchange: 交易所名称
        market_type: 市场类型
        timeframe: 回测 K 线周期
        strategy_config: 策略配置 JSON，包含策略名及参数
        start_date: 回测起始日期
        end_date: 回测结束日期
        initial_capital: 初始资金（USDT），默认 10000
        fee_rate: 手续费率，默认 0.1%
        slippage: 滑点比例，默认 0.05%
    """

    name: str = Field(..., max_length=100, description="回测任务名称")
    symbol: str = Field(..., description="交易对")
    exchange: str = Field(default="binance", description="交易所名称")
    market_type: str = Field(default="spot", description="市场类型")
    timeframe: str = Field(default="1h", description="K线周期")
    strategy_config: Dict[str, Any] = Field(
        ...,
        description="策略配置，如 {\"name\": \"macd_cross\", \"fast\": 12, \"slow\": 26}",
    )
    start_date: datetime = Field(..., description="回测起始日期")
    end_date: datetime = Field(..., description="回测结束日期")
    initial_capital: float = Field(
        default=10000.0,
        gt=0,
        description="初始资金（USDT）",
    )
    fee_rate: float = Field(
        default=0.001,
        ge=0,
        description="手续费率，如 0.001 = 0.1%",
    )
    slippage: float = Field(
        default=0.0005,
        ge=0,
        description="滑点比例，如 0.0005 = 0.05%",
    )


class BacktestTradeRecord(BaseModel):
    """
    回测成交记录模型

    回测过程中每笔模拟交易的详细记录。

    Attributes:
        direction: 交易方向（long / short）
        entry_time: 入场时间
        exit_time: 出场时间
        entry_price: 入场价格
        exit_price: 出场价格
        quantity: 交易数量
        pnl: 盈亏金额（USDT）
        pnl_ratio: 盈亏比例
        reason: 出场原因（如 止损、止盈、信号反转）
    """

    direction: str = Field(..., description="方向：long / short")
    entry_time: datetime = Field(..., description="入场时间")
    exit_time: datetime = Field(..., description="出场时间")
    entry_price: float = Field(..., description="入场价格")
    exit_price: float = Field(..., description="出场价格")
    quantity: float = Field(..., description="交易数量")
    pnl: float = Field(..., description="盈亏金额（USDT）")
    pnl_ratio: float = Field(..., description="盈亏比例")
    reason: str = Field(default="", description="出场原因")


class BacktestResult(BaseModel):
    """
    回测结果汇总模型

    整个回测周期的绩效指标和交易明细汇总。

    Attributes:
        total_return: 总收益率
        max_drawdown: 最大回撤
        win_rate: 胜率
        profit_loss_ratio: 盈亏比
        total_trades: 总交易笔数
        avg_holding_time: 平均持仓时间（秒）
        sharpe_ratio: 夏普比率
        trades: 完整成交记录列表
        equity_curve: 权益曲线数据点列表（用于绘图）
    """

    total_return: float = Field(..., description="总收益率")
    max_drawdown: float = Field(..., description="最大回撤")
    win_rate: float = Field(..., ge=0, le=1, description="胜率")
    profit_loss_ratio: float = Field(..., description="盈亏比")
    total_trades: int = Field(..., ge=0, description="总交易笔数")
    avg_holding_time: float = Field(..., description="平均持仓时间（秒）")
    sharpe_ratio: float = Field(..., description="夏普比率")
    trades: List[BacktestTradeRecord] = Field(
        default_factory=list,
        description="成交记录列表",
    )
    equity_curve: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="权益曲线，如 [{\"time\": \"...\", \"equity\": 10500}]",
    )


class BacktestResponse(BaseModel):
    """
    回测任务响应模型

    回测任务的完整状态，包含配置信息和执行结果。

    Attributes:
        id: 回测任务主键
        name: 任务名称
        symbol: 交易对
        status: 任务状态（pending / running / completed / failed）
        result: 回测结果，任务完成后填充
        created_at: 创建时间
    """

    # 支持从 ORM 对象直接转换
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="回测任务ID")
    name: str = Field(..., description="任务名称")
    symbol: str = Field(..., description="交易对")
    status: str = Field(
        default="pending",
        description="状态：pending / running / completed / failed",
    )
    result: Optional[BacktestResult] = Field(
        default=None,
        description="回测结果",
    )
    created_at: datetime = Field(..., description="创建时间")

"""
回测API路由。
提供回测任务的创建、查询和结果获取接口。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.backtest_task import BacktestTask
from app.models.backtest_trade import BacktestTrade
from app.models.market_kline import MarketKline
from app.schemas.backtest import BacktestRequest
from app.schemas.common import ResponseBase
from app.backtest.engine import BacktestEngine
from app.backtest.strategy_adapter import adapt_strategy_config
from app.backtest.reports import generate_text_report
import pandas as pd
from datetime import datetime

router = APIRouter()


@router.post("/run", response_model=ResponseBase, summary="运行回测")
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建并运行回测任务"""
    # 加载历史K线数据
    result = await db.execute(
        select(MarketKline)
        .where(
            MarketKline.symbol == request.symbol,
            MarketKline.interval == request.timeframe,
            MarketKline.open_time >= request.start_date,
            MarketKline.open_time <= request.end_date,
        )
        .order_by(MarketKline.open_time)
    )
    klines = result.scalars().all()

    if len(klines) < 100:
        return ResponseBase(
            code=400,
            message=f"K线数据不足，需要至少100根，当前只有{len(klines)}根。请先导入历史数据。",
        )

    # 转换为DataFrame
    kline_data = [
        {
            "open_time": k.open_time,
            "open": float(k.open) if k.open else 0,
            "high": float(k.high) if k.high else 0,
            "low": float(k.low) if k.low else 0,
            "close": float(k.close) if k.close else 0,
            "volume": float(k.volume) if k.volume else 0,
        }
        for k in klines
    ]
    kline_df = pd.DataFrame(kline_data)

    # 适配策略配置
    strategy_config = adapt_strategy_config(request.strategy_config or {})

    # 创建回测任务记录
    task = BacktestTask(
        name=request.name,
        symbol=request.symbol,
        exchange=request.exchange,
        market_type=request.market_type,
        timeframe=request.timeframe,
        strategy_config=strategy_config,
        date_range={
            "start": str(request.start_date),
            "end": str(request.end_date),
        },
        status="running",
        created_by=current_user.id,
    )
    db.add(task)
    await db.flush()

    # 运行回测
    try:
        engine = BacktestEngine(
            initial_capital=request.initial_capital,
            fee_rate=request.fee_rate,
            slippage=request.slippage,
        )
        bt_result = await engine.run(kline_df, strategy_config)

        # 保存回测交易明细
        for trade in bt_result.get("trades", []):
            bt_trade = BacktestTrade(
                task_id=task.id,
                symbol=request.symbol,
                direction=trade.get("direction", ""),
                entry_time=datetime.fromisoformat(trade["entry_time"])
                if trade.get("entry_time")
                else None,
                exit_time=datetime.fromisoformat(trade["exit_time"])
                if trade.get("exit_time")
                else None,
                entry_price=trade.get("entry_price", 0),
                exit_price=trade.get("exit_price", 0),
                quantity=trade.get("quantity", 0),
                pnl=trade.get("pnl", 0),
                pnl_ratio=trade.get("pnl_ratio", 0),
                reason=trade.get("reason", ""),
            )
            db.add(bt_trade)

        task.status = "completed"
        task.result_json = bt_result["metrics"]
        await db.flush()

        text_report = generate_text_report(bt_result)

        return ResponseBase(
            data={
                "task_id": task.id,
                "metrics": bt_result["metrics"],
                "trades_count": len(bt_result.get("trades", [])),
                "equity_curve_length": len(bt_result.get("equity_curve", [])),
                "text_report": text_report,
            }
        )

    except Exception as e:
        task.status = "failed"
        task.result_json = {"error": str(e)}
        await db.flush()
        return ResponseBase(code=500, message=f"回测运行失败: {e}")


@router.get("/tasks", response_model=ResponseBase, summary="获取回测任务列表")
async def list_backtest_tasks(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取回测任务列表"""
    result = await db.execute(
        select(BacktestTask).order_by(desc(BacktestTask.created_at)).limit(limit)
    )
    tasks = result.scalars().all()

    data = [
        {
            "id": t.id,
            "name": t.name,
            "symbol": t.symbol,
            "timeframe": t.timeframe,
            "status": t.status,
            "result_summary": t.result_json,
            "created_at": str(t.created_at),
        }
        for t in tasks
    ]
    return ResponseBase(data=data)


@router.get("/tasks/{task_id}", response_model=ResponseBase, summary="获取回测详情")
async def get_backtest_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取回测任务详情"""
    result = await db.execute(select(BacktestTask).where(BacktestTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="回测任务不存在")

    return ResponseBase(
        data={
            "id": task.id,
            "name": task.name,
            "symbol": task.symbol,
            "exchange": task.exchange,
            "market_type": task.market_type,
            "timeframe": task.timeframe,
            "strategy_config": task.strategy_config,
            "date_range": task.date_range,
            "status": task.status,
            "result": task.result_json,
            "created_at": str(task.created_at),
        }
    )


@router.get(
    "/tasks/{task_id}/trades", response_model=ResponseBase, summary="获取回测交易明细"
)
async def get_backtest_trades(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取回测任务的交易明细"""
    result = await db.execute(
        select(BacktestTrade)
        .where(BacktestTrade.task_id == task_id)
        .order_by(BacktestTrade.entry_time)
    )
    trades = result.scalars().all()

    data = [
        {
            "direction": t.direction,
            "entry_time": str(t.entry_time) if t.entry_time else None,
            "exit_time": str(t.exit_time) if t.exit_time else None,
            "entry_price": float(t.entry_price) if t.entry_price else 0,
            "exit_price": float(t.exit_price) if t.exit_price else 0,
            "quantity": float(t.quantity) if t.quantity else 0,
            "pnl": float(t.pnl) if t.pnl else 0,
            "pnl_ratio": float(t.pnl_ratio) if t.pnl_ratio else 0,
            "reason": t.reason,
        }
        for t in trades
    ]
    return ResponseBase(data=data)

"""
回测API路由。
提供回测任务的创建、查询和结果获取接口。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from copy import deepcopy
from typing import Any, Dict, List

from sqlalchemy import select, desc, and_
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.backtest_task import BacktestTask
from app.models.backtest_trade import BacktestTrade
from app.models.market_kline import MarketKline
from app.schemas.backtest import BacktestRequest
from app.schemas.common import ResponseBase
from app.backtest.engine import BacktestEngine
from app.backtest.strategy_adapter import (
    adapt_strategy_config,
    get_strategy_factors,
    get_strategy_indicators,
)
from app.backtest.reports import generate_text_report
from app.services.backtest_strategy_presets import (
    deep_merge_strategy_dict,
    get_backtest_strategy_preset_service,
)
from app.services.market_data_provider import market_data_provider
import pandas as pd
from datetime import datetime

router = APIRouter()


@router.get("/strategies", response_model=ResponseBase, summary="列出回测策略预设")
async def list_backtest_strategies(
    _user: User = Depends(get_current_user),
):
    """
    Scan ``config/backtest_strategies/*.yaml`` for presets (short TTL cache).

    Returns id / display_name / description for UI dropdowns.
    """
    service = get_backtest_strategy_preset_service()
    return ResponseBase(data=service.list_summaries())


@router.post("/run", response_model=ResponseBase, summary="运行回测")
async def run_backtest(
    request: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    source_mode: str = Query(
        "cache",
        description="数据模式：cache=读缓存；live=实时拉取K线并回写缓存（当前按时间窗口估算需要K线条数）",
    ),
):
    """创建并运行回测任务"""
    preset_id = request.strategy_preset_id
    task_name = (request.name or "").strip()
    merged_raw: Dict[str, Any]

    if preset_id:
        try:
            preset = get_backtest_strategy_preset_service().get_preset_by_id(
                preset_id
            )
        except KeyError:
            return ResponseBase(
                code=400,
                message=f"未知策略预设: {preset_id}",
            )
        merged_raw = deep_merge_strategy_dict(
            preset["strategy_config"],
            request.strategy_config,
        )
        if not task_name:
            task_name = preset["display_name"]
    else:
        merged_raw = deepcopy(request.strategy_config or {})

    if not task_name:
        task_name = "Backtest"

    strategy_config = adapt_strategy_config(merged_raw)

    if source_mode not in ("cache", "live"):
        raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")

    klines: List[Dict[str, Any]] = []
    if source_mode == "live":
        # ---- live 模式：从 exchange 拉取“足够覆盖时间范围”的K线，再在本地过滤窗口 ----
        interval_seconds_map = {
            "1m": 60,
            "3m": 180,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "2h": 7200,
            "4h": 14400,
            "6h": 21600,
            "8h": 28800,
            "12h": 43200,
            "1d": 86400,
        }
        interval_seconds = interval_seconds_map.get(request.timeframe, 3600)
        total_seconds = max(0.0, (request.end_date - request.start_date).total_seconds())
        needed_bars = int(total_seconds // interval_seconds) + 2

        # 适当冗余，避免边界导致 K 线不足
        fetch_limit = max(100, int(needed_bars * 1.2))
        fetch_limit = min(fetch_limit, 2000)

        klines = await market_data_provider.get_klines(
            db,
            exchange=request.exchange,
            market_type=request.market_type,
            symbol=request.symbol,
            interval=request.timeframe,
            limit=fetch_limit,
            source_mode="live",
            persist_to_db=True,
        )

        filtered = [
            k
            for k in klines
            if request.start_date <= k["open_time"] <= request.end_date
        ]
        klines = filtered
    else:
        # ---- cache 模式：从数据库加载时间窗口内的K线 ----
        result = await db.execute(
            select(MarketKline)
            .where(
                and_(
                    MarketKline.exchange == request.exchange,
                    MarketKline.symbol == request.symbol,
                    MarketKline.market_type == request.market_type,
                    MarketKline.interval == request.timeframe,
                    MarketKline.open_time >= request.start_date,
                    MarketKline.open_time <= request.end_date,
                )
            )
            .order_by(MarketKline.open_time)
        )
        orm_klines = result.scalars().all()
        klines = [
            {
                "open_time": k.open_time,
                "open": float(k.open) if k.open else 0.0,
                "high": float(k.high) if k.high else 0.0,
                "low": float(k.low) if k.low else 0.0,
                "close": float(k.close) if k.close else 0.0,
                "volume": float(k.volume) if k.volume else 0.0,
            }
            for k in orm_klines
        ]

    if len(klines) < 100:
        return ResponseBase(
            code=400,
            message=f"K线数据不足，需要至少100根，当前只有{len(klines)}根。请先导入历史数据。",
        )

    kline_df = pd.DataFrame(
        [
            {
                "open_time": k["open_time"],
                "open": k["open"],
                "high": k["high"],
                "low": k["low"],
                "close": k["close"],
                "volume": k.get("volume", 0.0),
            }
            for k in klines
        ]
    )

    # 创建回测任务记录
    task = BacktestTask(
        name=task_name,
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
        bt_result = await engine.run(
            kline_df,
            strategy_config,
            indicator_keys=get_strategy_indicators(strategy_config),
            factor_keys=get_strategy_factors(strategy_config),
        )

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

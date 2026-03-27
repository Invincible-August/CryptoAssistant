"""
交易建议API路由。
提供交易建议查询和生成接口。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.signal_recommendation import SignalRecommendation
from app.schemas.common import ResponseBase

router = APIRouter()


@router.get("/latest", response_model=ResponseBase, summary="获取最新交易建议")
async def get_latest_signal(
    symbol: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取最新的交易建议"""
    result = await db.execute(
        select(SignalRecommendation)
        .where(SignalRecommendation.symbol == symbol)
        .order_by(desc(SignalRecommendation.created_at))
        .limit(1)
    )
    signal = result.scalar_one_or_none()

    if not signal:
        return ResponseBase(data=None, message="暂无交易建议")

    return ResponseBase(
        data={
            "id": signal.id,
            "symbol": signal.symbol,
            "direction": signal.direction,
            "confidence": float(signal.confidence) if signal.confidence else 0,
            "win_rate": float(signal.win_rate) if signal.win_rate else 0,
            "entry_zone": signal.entry_zone,
            "stop_loss": float(signal.stop_loss) if signal.stop_loss else 0,
            "take_profits": signal.take_profits,
            "tp_strategy": signal.tp_strategy,
            "risks": signal.risks_json,
            "reasons": signal.reasons_json,
            "summary": signal.summary,
            "created_at": str(signal.created_at),
        }
    )


@router.get("/history", response_model=ResponseBase, summary="获取建议历史")
async def get_signal_history(
    symbol: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取交易建议历史"""
    result = await db.execute(
        select(SignalRecommendation)
        .where(SignalRecommendation.symbol == symbol)
        .order_by(desc(SignalRecommendation.created_at))
        .limit(limit)
    )
    signals = result.scalars().all()

    data = [
        {
            "id": s.id,
            "direction": s.direction,
            "confidence": float(s.confidence) if s.confidence else 0,
            "win_rate": float(s.win_rate) if s.win_rate else 0,
            "summary": s.summary,
            "created_at": str(s.created_at),
        }
        for s in signals
    ]
    return ResponseBase(data=data)


@router.post("/generate", response_model=ResponseBase, summary="生成交易建议")
async def generate_signal(
    symbol: str = Query(...),
    exchange: str = Query("binance"),
    market_type: str = Query("spot"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """基于当前市场数据生成新的交易建议"""
    from app.services.analysis_service import run_full_analysis

    try:
        result = await run_full_analysis(
            db=db,
            symbol=symbol,
            exchange=exchange,
            market_type=market_type,
        )
        return ResponseBase(data=result)
    except Exception as e:
        return ResponseBase(code=500, message=f"生成建议失败: {e}")

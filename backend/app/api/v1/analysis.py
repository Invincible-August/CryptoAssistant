"""
行为分析API路由。
提供市场行为分析、主导资金推断等接口。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.analysis_snapshot import AnalysisSnapshot
from app.schemas.common import ResponseBase
from app.schemas.analysis import AnalysisRequest

router = APIRouter()


@router.post("/run", response_model=ResponseBase, summary="运行行为分析")
async def run_analysis(
    request: AnalysisRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """运行完整的市场行为分析（评分+推断+建议）"""
    from app.services.analysis_service import run_full_analysis

    try:
        result = await run_full_analysis(
            db=db,
            symbol=request.symbol,
            exchange=request.exchange,
            market_type=request.market_type,
            timeframe=request.timeframe,
        )
        return ResponseBase(data=result)
    except Exception as e:
        return ResponseBase(code=500, message=f"分析失败: {e}")


@router.get("/latest", response_model=ResponseBase, summary="获取最新分析")
async def get_latest_analysis(
    symbol: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取指定交易对的最新分析快照"""
    result = await db.execute(
        select(AnalysisSnapshot)
        .where(AnalysisSnapshot.symbol == symbol)
        .order_by(desc(AnalysisSnapshot.created_at))
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()

    if not snapshot:
        return ResponseBase(data=None, message="暂无分析数据")

    return ResponseBase(
        data={
            "id": snapshot.id,
            "symbol": snapshot.symbol,
            "stage": snapshot.stage,
            "scores": snapshot.scores_json,
            "hypotheses": snapshot.hypotheses_json,
            "evidence": snapshot.evidence_json,
            "risks": snapshot.risks_json,
            "summary": snapshot.summary,
            "event_time": str(snapshot.event_time),
        }
    )


@router.get("/history", response_model=ResponseBase, summary="获取分析历史")
async def get_analysis_history(
    symbol: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取分析历史记录"""
    result = await db.execute(
        select(AnalysisSnapshot)
        .where(AnalysisSnapshot.symbol == symbol)
        .order_by(desc(AnalysisSnapshot.created_at))
        .limit(limit)
    )
    snapshots = result.scalars().all()

    data = [
        {
            "id": s.id,
            "stage": s.stage,
            "summary": s.summary,
            "event_time": str(s.event_time),
            "created_at": str(s.created_at),
        }
        for s in snapshots
    ]
    return ResponseBase(data=data)

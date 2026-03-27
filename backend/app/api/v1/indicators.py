"""
技术指标API路由。
提供指标列表查询、指标计算和结果查询接口。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.indicator_result import IndicatorResult
from app.indicators.registry import indicator_registry
from app.schemas.common import ResponseBase
from app.schemas.indicators import IndicatorCalcRequest

router = APIRouter()


@router.get("/", response_model=ResponseBase, summary="获取所有指标列表")
async def list_indicators(
    source: str = Query(None, description="按来源过滤: system/human/ai"),
    _user: User = Depends(get_current_user),
):
    """获取所有已注册的指标元数据"""
    if source:
        indicators = indicator_registry.list_by_source(source)
    else:
        indicators = indicator_registry.list_all()
    return ResponseBase(data=indicators)


@router.get("/{key}/meta", response_model=ResponseBase, summary="获取指标元数据")
async def get_indicator_meta(
    key: str,
    _user: User = Depends(get_current_user),
):
    """获取指定指标的元数据"""
    try:
        indicator_cls = indicator_registry.get(key)
        return ResponseBase(data=indicator_cls.get_metadata())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"指标 {key} 不存在")


@router.post("/calculate", response_model=ResponseBase, summary="计算指标")
async def calculate_indicator(
    request: IndicatorCalcRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """计算指定指标并返回结果"""
    from app.services.indicator_service import calculate_indicator as calc

    try:
        result = await calc(
            db=db,
            indicator_key=request.indicator_key,
            symbol=request.symbol,
            exchange=request.exchange,
            market_type=request.market_type,
            timeframe=request.timeframe,
            params=request.params or {},
        )
        return ResponseBase(data=result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"指标计算失败: {e}")


@router.get("/results", response_model=ResponseBase, summary="查询指标结果")
async def get_indicator_results(
    symbol: str = Query(...),
    indicator_key: str = Query(...),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """查询已保存的指标计算结果"""
    result = await db.execute(
        select(IndicatorResult)
        .where(
            IndicatorResult.symbol == symbol,
            IndicatorResult.indicator_key == indicator_key,
        )
        .order_by(desc(IndicatorResult.event_time))
        .limit(limit)
    )
    results = result.scalars().all()

    data = [
        {
            "indicator_key": r.indicator_key,
            "source": r.source,
            "timeframe": r.timeframe,
            "event_time": str(r.event_time),
            "result": r.result_json,
        }
        for r in results
    ]
    return ResponseBase(data=data)

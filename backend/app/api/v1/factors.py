"""
量化因子API路由。
提供因子列表查询、因子计算和结果查询接口。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.factor_result import FactorResult
from app.factors.registry import FactorRegistry as factor_registry
from app.schemas.common import ResponseBase
from app.schemas.factors import FactorCalcRequest

router = APIRouter()


@router.get("/", response_model=ResponseBase, summary="获取所有因子列表")
async def list_factors(
    source: str = Query(None, description="按来源过滤"),
    _user: User = Depends(get_current_user),
):
    """获取所有已注册的因子元数据"""
    factors = factor_registry.list_metadata()
    if source:
        factors = [f for f in factors if f.get("source") == source]
    return ResponseBase(data=factors)


@router.get("/{key}/meta", response_model=ResponseBase, summary="获取因子元数据")
async def get_factor_meta(
    key: str,
    _user: User = Depends(get_current_user),
):
    """获取指定因子的元数据"""
    try:
        factor_cls = factor_registry.get(key)
        return ResponseBase(data=factor_cls.get_metadata())
    except KeyError:
        raise HTTPException(status_code=404, detail=f"因子 {key} 不存在")


@router.post("/calculate", response_model=ResponseBase, summary="计算因子")
async def calculate_factor(
    request: FactorCalcRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """计算指定因子并返回结果"""
    from app.services.factor_service import calculate_factor as calc

    try:
        result = await calc(
            db=db,
            factor_key=request.factor_key,
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
        raise HTTPException(status_code=500, detail=f"因子计算失败: {e}")


@router.get("/results", response_model=ResponseBase, summary="查询因子结果")
async def get_factor_results(
    symbol: str = Query(...),
    factor_key: str = Query(...),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """查询已保存的因子计算结果"""
    result = await db.execute(
        select(FactorResult)
        .where(
            FactorResult.symbol == symbol,
            FactorResult.factor_key == factor_key,
        )
        .order_by(desc(FactorResult.event_time))
        .limit(limit)
    )
    results = result.scalars().all()

    data = [
        {
            "factor_key": r.factor_key,
            "source": r.source,
            "timeframe": r.timeframe,
            "event_time": str(r.event_time),
            "result": r.result_json,
        }
        for r in results
    ]
    return ResponseBase(data=data)

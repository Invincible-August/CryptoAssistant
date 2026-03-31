"""
量化因子API路由。
提供因子列表查询、因子计算和结果查询接口。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user, get_admin_user
from app.models.user import User
from app.models.factor_result import FactorResult
from app.factors.registry import FactorRegistry as factor_registry
from app.schemas.common import ResponseBase
from app.schemas.factors import FactorCalcRequest, FactorPluginLoadRequest
from app.services.plugin_runtime_service import get_plugin_runtime_service

router = APIRouter()


def _attach_factor_load_flags(metadata_list: list) -> list:
    """Merge ``load_enabled`` from plugin_runtime into factor metadata dicts."""
    runtime = get_plugin_runtime_service()
    disabled = runtime.get_disabled_factors()
    out = []
    for meta in metadata_list:
        row = dict(meta) if isinstance(meta, dict) else dict(meta)
        fk = row.get("factor_key", "")
        row["load_enabled"] = fk not in disabled
        out.append(row)
    return out


@router.get("/", response_model=ResponseBase, summary="获取所有因子列表")
async def list_factors(
    source: str = Query(None, description="按来源过滤"),
    _user: User = Depends(get_current_user),
):
    """获取所有已注册的因子元数据"""
    factors = factor_registry.list_metadata()
    if source:
        factors = [f for f in factors if f.get("source") == source]
    factors = _attach_factor_load_flags(factors)
    return ResponseBase(data=factors)


@router.get("/{key}/meta", response_model=ResponseBase, summary="获取因子元数据")
async def get_factor_meta(
    key: str,
    _user: User = Depends(get_current_user),
):
    """获取指定因子的元数据"""
    factor_cls = factor_registry.get(key)
    if factor_cls is None:
        raise HTTPException(status_code=404, detail=f"因子 {key} 不存在")
    meta = factor_cls.get_metadata()
    enriched = _attach_factor_load_flags([meta])[0]
    return ResponseBase(data=enriched)


@router.post("/calculate", response_model=ResponseBase, summary="计算因子")
async def calculate_factor(
    request: FactorCalcRequest,
    db: AsyncSession = Depends(get_db),
    source_mode: str = Query(
        "cache",
        description="数据模式：cache=读缓存；live=实时拉取交易所并可回写缓存",
    ),
    _user: User = Depends(get_current_user),
):
    """计算指定因子并返回结果"""
    from app.services.factor_service import calculate_factor as calc

    try:
        if source_mode not in ("cache", "live"):
            raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")
        result = await calc(
            db=db,
            factor_key=request.factor_key,
            symbol=request.symbol,
            exchange=request.exchange,
            market_type=request.market_type,
            timeframe=request.timeframe,
            params=request.params or {},
            source_mode=source_mode,
        )
        return ResponseBase(data=result)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"因子计算失败: {e}")


@router.patch(
    "/runtime/load-enabled",
    response_model=ResponseBase,
    summary="设置因子是否参与计算（写入 plugin_runtime.yaml）",
)
async def set_factor_load_enabled(
    body: FactorPluginLoadRequest,
    _admin: User = Depends(get_admin_user),
):
    """
    Persist factor load flag. Requires admin role.

    Disabled factors stay visible in ``GET /factors/`` with ``load_enabled=false``.
    """
    factor_cls = factor_registry.get(body.factor_key)
    if factor_cls is None:
        raise HTTPException(
            status_code=404,
            detail=f"未知因子: {body.factor_key}",
        )
    runtime = get_plugin_runtime_service()
    runtime.set_factor_disabled(body.factor_key, disabled=not body.load_enabled)
    return ResponseBase(
        data={
            "factor_key": body.factor_key,
            "load_enabled": body.load_enabled,
        }
    )


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

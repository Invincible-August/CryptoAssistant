"""
技术指标API路由。
提供指标列表查询、指标计算和结果查询接口。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user, get_admin_user
from app.models.user import User
from app.models.indicator_result import IndicatorResult
from app.indicators.registry import indicator_registry
from app.schemas.common import ResponseBase
from app.schemas.indicators import IndicatorCalcRequest, IndicatorPluginLoadRequest
from app.services.plugin_runtime_service import get_plugin_runtime_service

router = APIRouter()


def _attach_indicator_load_flags(metadata_list: list) -> list:
    """Merge ``load_enabled`` from plugin_runtime into indicator metadata dicts."""
    runtime = get_plugin_runtime_service()
    disabled = runtime.get_disabled_indicators()
    out = []
    for meta in metadata_list:
        row = dict(meta) if isinstance(meta, dict) else dict(meta)
        ik = row.get("indicator_key", "")
        row["load_enabled"] = ik not in disabled
        out.append(row)
    return out


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
    indicators = _attach_indicator_load_flags(indicators)
    return ResponseBase(data=indicators)


@router.get("/{key}/meta", response_model=ResponseBase, summary="获取指标元数据")
async def get_indicator_meta(
    key: str,
    _user: User = Depends(get_current_user),
):
    """获取指定指标的元数据"""
    try:
        indicator_cls = indicator_registry.get(key)
        meta = indicator_cls.get_metadata()
        enriched = _attach_indicator_load_flags([meta])[0]
        return ResponseBase(data=enriched)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"指标 {key} 不存在")


@router.post("/calculate", response_model=ResponseBase, summary="计算指标")
async def calculate_indicator(
    request: IndicatorCalcRequest,
    db: AsyncSession = Depends(get_db),
    source_mode: str = Query(
        "cache",
        description="数据模式：cache=读缓存；live=实时拉取交易所并可回写缓存",
    ),
    _user: User = Depends(get_current_user),
):
    """计算指定指标并返回结果"""
    from app.services.indicator_service import calculate_indicator as calc

    try:
        if source_mode not in ("cache", "live"):
            raise HTTPException(status_code=400, detail="source_mode 必须为 cache 或 live")
        result = await calc(
            db=db,
            indicator_key=request.indicator_key,
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
        raise HTTPException(status_code=500, detail=f"指标计算失败: {e}")


@router.patch(
    "/runtime/load-enabled",
    response_model=ResponseBase,
    summary="设置指标是否参与计算（写入 plugin_runtime.yaml）",
)
async def set_indicator_load_enabled(
    body: IndicatorPluginLoadRequest,
    _admin: User = Depends(get_admin_user),
):
    """Persist indicator load flag (admin only)."""
    try:
        indicator_registry.get(body.indicator_key)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"未知指标: {body.indicator_key}",
        )
    runtime = get_plugin_runtime_service()
    runtime.set_indicator_disabled(
        body.indicator_key,
        disabled=not body.load_enabled,
    )
    return ResponseBase(
        data={
            "indicator_key": body.indicator_key,
            "load_enabled": body.load_enabled,
        }
    )


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

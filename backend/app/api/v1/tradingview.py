"""
TradingView集成API路由。
提供Webhook接收和图表数据兼容接口。
"""
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.core.config import settings
from app.schemas.common import ResponseBase

router = APIRouter()


def _check_tv_enabled():
    """检查TradingView模块是否启用"""
    if not settings.MODULE_TRADINGVIEW_ENABLED:
        raise HTTPException(status_code=403, detail="TradingView模块未启用")


@router.post("/webhook", response_model=ResponseBase, summary="接收TradingView Webhook")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    接收TradingView警报Webhook。
    此接口不需要JWT认证（TradingView无法携带Bearer Token），
    但通过webhook secret验证身份。
    """
    _check_tv_enabled()

    payload_body = await request.body()
    try:
        body = await request.json()
    except Exception:
        body = {"raw": payload_body.decode("utf-8", errors="replace")}

    from app.tradingview.service import TradingViewService

    try:
        service = TradingViewService()
        result = await service.process_webhook(
            payload_body=payload_body,
            payload_dict=body,
        )
        return ResponseBase(data=result)
    except Exception as e:
        return ResponseBase(code=500, message=f"Webhook处理失败: {e}")


@router.get("/chart-data", response_model=ResponseBase, summary="获取TV兼容图表数据")
async def get_chart_data(
    symbol: str = Query(...),
    timeframe: str = Query("1h"),
    limit: int = Query(300, ge=1, le=2000),
    _user: User = Depends(get_current_user),
):
    """获取TradingView Lightweight Charts兼容格式的数据"""
    _check_tv_enabled()

    from app.tradingview.service import TradingViewService

    try:
        service = TradingViewService()
        data = await service.get_chart_data(
            symbol=symbol,
            timeframe=timeframe,
        )
        return ResponseBase(data=data)
    except Exception as e:
        return ResponseBase(code=500, message=f"获取图表数据失败: {e}")

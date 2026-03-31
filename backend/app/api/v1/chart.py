"""
图表分析 API。

提供 K 线 + 可选技术指标的 Lightweight Charts 兼容 JSON，供前端仅负责渲染。
不依赖 TradingView webhook/兼容接口。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ResponseBase
from app.services.chart_data_service import build_lightweight_chart_bundle

router = APIRouter()


@router.get(
    "/bundle",
    response_model=ResponseBase,
    summary="获取 K 线与可选指标的图表数据包",
)
async def get_chart_bundle(
    symbol: str = Query(..., description="交易对，如 BTCUSDT"),
    timeframe: str = Query("1h", description="K 线周期，如 1h / 4h / 1d"),
    exchange: str = Query("binance", description="交易所标识"),
    market_type: str = Query("spot", description="市场类型 spot / futures"),
    limit: int = Query(500, ge=50, le=2000, description="加载 K 线条数（升序）"),
    source_mode: str = Query(
        "cache",
        description="数据模式：cache=读缓存(数据库/Redis)；live=实时拉取交易所并可回写缓存",
    ),
    force_refresh: Optional[bool] = Query(
        None,
        description="兼容别名：true=等价 source_mode=live",
    ),
    indicators: Optional[str] = Query(
        None,
        description="逗号分隔的指标 key，如 ema,rsi；留空则仅返回 K 线",
    ),
    theme: str = Query("dark", description="图表主题 dark / light"),
    use_proxy: Optional[bool] = Query(
        None,
        description="是否通过 HTTP 代理访问交易所；不传则使用 env：BINANCE_PROXY_ENABLED",
    ),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """
    返回 config、candlestick、overlays、subcharts，供 Lightweight Charts 直接消费。

    指标在服务端内存计算，不落库 IndicatorResult。
    """
    keys_list: list[str] = []
    if indicators:
        keys_list = [k.strip() for k in indicators.split(",") if k.strip()]

    if force_refresh is True:
        source_mode = "live"

    if source_mode not in ("cache", "live"):
        return ResponseBase(
            code=400,
            message="source_mode 必须为 cache 或 live",
            data=None,
        )

    try:
        # use_proxy=None => 采用 env 默认值，让海外部署默认关闭代理。
        effective_use_proxy = (
            settings.BINANCE_PROXY_ENABLED
            if use_proxy is None
            else use_proxy
        )
        bundle = await build_lightweight_chart_bundle(
            db,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            indicator_keys=keys_list,
            theme=theme,
            source_mode=source_mode,  # cache/live
            use_proxy=effective_use_proxy,
        )
        return ResponseBase(data=bundle)
    except ValueError as err:
        logger.warning("图表数据请求无法完成: %s", err)
        return ResponseBase(code=400, message=str(err), data=None)

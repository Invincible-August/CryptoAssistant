"""
API路由汇总模块。
注册所有v1版本的API路由。
"""
from fastapi import APIRouter
from app.api.v1 import (
    auth,
    users,
    monitor,
    market,
    indicators,
    factors,
    analysis,
    signals,
    backtest,
    execution,
    ai,
    tradingview,
    config,
    logs,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(monitor.router, prefix="/monitor", tags=["实时监控"])
api_router.include_router(market.router, prefix="/market", tags=["行情数据"])
api_router.include_router(indicators.router, prefix="/indicators", tags=["技术指标"])
api_router.include_router(factors.router, prefix="/factors", tags=["量化因子"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["行为分析"])
api_router.include_router(signals.router, prefix="/signals", tags=["交易建议"])
api_router.include_router(backtest.router, prefix="/backtest", tags=["回测"])
api_router.include_router(execution.router, prefix="/execution", tags=["执行辅助"])
api_router.include_router(ai.router, prefix="/ai", tags=["AI分析"])
api_router.include_router(tradingview.router, prefix="/tradingview", tags=["TradingView"])
api_router.include_router(config.router, prefix="/config", tags=["系统配置"])
api_router.include_router(logs.router, prefix="/logs", tags=["系统日志"])

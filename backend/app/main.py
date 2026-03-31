"""
应用入口模块。
创建FastAPI应用实例，注册路由、中间件、事件处理器。
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.redis import redis_manager
from app.core.logging import setup_logging
from app.core.exceptions import AppException
from app.api.router import api_router
from app.indicators import register_all_indicators
from app.factors import register_all_factors
from app.datafeeds.runtime import init_datafeeds
from loguru import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # === 启动阶段 ===
    setup_logging()
    logger.info("=" * 50)
    logger.info(f"  {settings.APP_NAME} 启动中...")
    logger.info(f"  环境: {settings.APP_ENV}")
    logger.info("=" * 50)

    # 初始化数据库
    await init_db()
    logger.info("数据库初始化完成")

    # 连接Redis
    try:
        await redis_manager.connect()
        logger.info("Redis连接成功")
    except Exception as e:
        logger.warning(f"Redis连接失败，系统将不使用缓存: {e}")

    # 注册指标和因子插件
    register_all_indicators()
    register_all_factors()
    logger.info("指标和因子插件注册完成")

    # 初始化交易所数据源（用于实时拉取 A 模式）
    try:
        await init_datafeeds()
    except Exception as exc:  # noqa: BLE001
        logger.warning("数据源初始化失败，系统仍可使用缓存模式: %s", exc)

    logger.info(f"系统启动完成 - 访问 http://{settings.APP_HOST}:{settings.APP_PORT}/docs 查看API文档")

    yield

    # === 关闭阶段 ===
    logger.info("系统关闭中...")
    await redis_manager.disconnect()
    await close_db()
    logger.info("系统已安全关闭")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    description="事件驱动型加密货币交易辅助系统 MVP",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理器
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """处理自定义应用异常"""
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "message": exc.message, "data": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "系统内部错误", "data": None},
    )


# 注册API路由
app.include_router(api_router, prefix="/api/v1")


# 健康检查
@app.get("/health", tags=["系统"])
async def health_check():
    """系统健康检查"""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }

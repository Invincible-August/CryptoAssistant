"""
应用全局配置模块。
使用 pydantic-settings 从环境变量和 .env 文件加载配置。
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """系统全局配置类，所有配置项从环境变量或.env文件加载"""

    # ==================== 应用基础配置 ====================
    APP_NAME: str = "CryptoAssistant"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 默认令牌有效期：24小时

    # ==================== 数据库配置 ====================
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_assistant"
    DATABASE_ECHO: bool = False  # 是否打印SQL语句（调试用）

    # ==================== Redis配置 ====================
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""

    # ==================== Binance交易所配置 ====================
    # 重要：绝对不要在代码中硬编码密钥，务必通过.env文件配置
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET: bool = True  # 默认使用测试网，生产环境需关闭
    # 可选：REST 层 use_proxy=True 时，在 BINANCE_PROXY_ENABLED=true 且 URL 非空时优先使用（默认与本项目常见本地代理端口一致）
    BINANCE_PROXY_ENABLED: bool = False
    BINANCE_PROXY_URL: str = "http://127.0.0.1:7890"

    # ==================== OpenAI配置 ====================
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ==================== 模块开关 ====================
    MODULE_AI_ENABLED: bool = False          # AI助手模块
    MODULE_TRADINGVIEW_ENABLED: bool = False  # TradingView信号接收模块
    MODULE_EXECUTION_ENABLED: bool = False    # 自动下单执行模块
    MODULE_BACKTEST_ENABLED: bool = True      # 回测模块（默认启用）

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # ==================== 前端配置 ====================
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ==================== 默认管理员账户 ====================
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123456"
    ADMIN_EMAIL: str = "admin@example.com"

    model_config = {
        "env_file": [".env", "../.env"],
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# 全局配置单例，应用启动时自动从环境变量/.env加载
settings = Settings()

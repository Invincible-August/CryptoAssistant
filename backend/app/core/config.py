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
    BINANCE_TESTNET: bool = False  # 默认使用主网（测试网 WebSocket 端点在部分环境下可能不可用）

    # ==================== Binance 网络代理（WebSocket/REST 通用开关） ====================
    # 中国大陆网络环境下通常需要走本地 HTTP 代理（例如 Clash/Surge）。
    # 海外服务器部署时可将开关置为 false，避免不必要的代理链路。
    BINANCE_PROXY_ENABLED: bool = False
    BINANCE_PROXY_URL: str = "http://127.0.0.1:7890"

    # ==================== OpenAI配置 ====================
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ==================== 插件热重载 ====================
    # 生产环境可设为 False，禁止 POST /admin/plugins/reload
    PLUGIN_HOT_RELOAD_ENABLED: bool = True

    # ==================== 模块开关 ====================
    MODULE_AI_ENABLED: bool = False          # AI助手模块
    MODULE_EXECUTION_ENABLED: bool = False    # 自动下单执行模块
    MODULE_BACKTEST_ENABLED: bool = True      # 回测模块（默认启用）

    # ==================== 日志配置 ====================
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # ==================== 行情自动增量更新（symbol_watches -> 1m backfill） ====================
    # 说明：
    # - enabled 为总开关；关闭时不会注册定时任务；
    # - default_minutes 为全局默认拉取周期（分钟），可被单条 watch 的 config_json.update_minutes 覆盖；
    # - safety_lookback_minutes 为安全回看（分钟），用于每次增量回补时向前多拉一小段，防止边界漏数据/延迟写入；
    # - 所有时间语义统一按 UTC，并按“已完成分钟”对齐（见 spec）。
    MARKET_AUTO_UPDATE_ENABLED: bool = True
    MARKET_AUTO_UPDATE_DEFAULT_MINUTES: int = 1
    MARKET_AUTO_UPDATE_SAFETY_LOOKBACK_MINUTES: int = 3

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
        # 允许忽略已移除模块遗留的环境变量（例如 TradingView 已移除后仍可能残留 MODULE_TRADINGVIEW_ENABLED）。
        "extra": "ignore",
    }


# 全局配置单例，应用启动时自动从环境变量/.env加载
settings = Settings()

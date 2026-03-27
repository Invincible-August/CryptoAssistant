"""
数据模型（Schemas）统一入口

集中导出所有 Pydantic 数据模型，方便各业务模块按需导入。
使用示例：
    from app.schemas import LoginRequest, UserResponse, KlineData
"""

# ── 通用响应 ──────────────────────────────────────────────
from app.schemas.common import (
    PageParams,
    ResponseBase,
    ResponseList,
)

# ── 认证鉴权 ──────────────────────────────────────────────
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    TokenPayload,
)

# ── 用户管理 ──────────────────────────────────────────────
from app.schemas.user import (
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)

# ── 行情数据 ──────────────────────────────────────────────
from app.schemas.market import (
    FundingData,
    KlineData,
    MarketOverview,
    OpenInterestData,
    OrderbookData,
    TradeData,
)

# ── 监控管理 ──────────────────────────────────────────────
from app.schemas.monitor import (
    RealtimeStatus,
    SymbolWatchCreate,
    SymbolWatchResponse,
    SymbolWatchUpdate,
)

# ── 技术指标 ──────────────────────────────────────────────
from app.schemas.indicators import (
    IndicatorCalcRequest,
    IndicatorCalcResponse,
    IndicatorMeta,
)

# ── 量化因子 ──────────────────────────────────────────────
from app.schemas.factors import (
    FactorCalcRequest,
    FactorCalcResponse,
    FactorMeta,
)

# ── 行为分析 ──────────────────────────────────────────────
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    BehaviorProfile,
)

# ── 交易信号 ──────────────────────────────────────────────
from app.schemas.signals import (
    SignalRecommendation,
    SignalResponse,
    TakeProfit,
)

# ── AI 分析 ───────────────────────────────────────────────
from app.schemas.ai import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    AIArtifactProposal,
    AIArtifactResponse,
    AIFeedbackRequest,
)

# ── 回测系统 ──────────────────────────────────────────────
from app.schemas.backtest import (
    BacktestRequest,
    BacktestResponse,
    BacktestResult,
    BacktestTradeRecord,
)

# ── 订单执行 ──────────────────────────────────────────────
from app.schemas.execution import (
    OrderFillResponse,
    OrderRequest,
    OrderResponse,
)

# ── 系统配置 ──────────────────────────────────────────────
from app.schemas.config import (
    ModuleConfigResponse,
    ModuleConfigUpdate,
    SystemConfigResponse,
)

__all__ = [
    # 通用
    "ResponseBase",
    "ResponseList",
    "PageParams",
    # 认证
    "LoginRequest",
    "LoginResponse",
    "TokenPayload",
    # 用户
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    # 行情
    "KlineData",
    "TradeData",
    "OrderbookData",
    "FundingData",
    "OpenInterestData",
    "MarketOverview",
    # 监控
    "SymbolWatchCreate",
    "SymbolWatchUpdate",
    "SymbolWatchResponse",
    "RealtimeStatus",
    # 指标
    "IndicatorMeta",
    "IndicatorCalcRequest",
    "IndicatorCalcResponse",
    # 因子
    "FactorMeta",
    "FactorCalcRequest",
    "FactorCalcResponse",
    # 分析
    "AnalysisRequest",
    "AnalysisResponse",
    "BehaviorProfile",
    # 信号
    "TakeProfit",
    "SignalRecommendation",
    "SignalResponse",
    # AI
    "AIAnalysisRequest",
    "AIAnalysisResponse",
    "AIFeedbackRequest",
    "AIArtifactProposal",
    "AIArtifactResponse",
    # 回测
    "BacktestRequest",
    "BacktestTradeRecord",
    "BacktestResult",
    "BacktestResponse",
    # 执行
    "OrderRequest",
    "OrderResponse",
    "OrderFillResponse",
    # 配置
    "ModuleConfigUpdate",
    "ModuleConfigResponse",
    "SystemConfigResponse",
]

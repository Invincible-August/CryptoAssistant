"""
数据库模型包。
导入所有模型类，确保Alembic能够发现它们。
"""
from app.models.user import User
from app.models.module_config import ModuleConfig
from app.models.exchange_config import ExchangeConfig
from app.models.symbol_watch import SymbolWatch
from app.models.market_kline import MarketKline
from app.models.market_trade import MarketTrade
from app.models.market_orderbook_snapshot import MarketOrderbookSnapshot
from app.models.market_funding import MarketFunding
from app.models.market_open_interest import MarketOpenInterest
from app.models.indicator_definition import IndicatorDefinition
from app.models.factor_definition import FactorDefinition
from app.models.indicator_result import IndicatorResult
from app.models.factor_result import FactorResult
from app.models.analysis_snapshot import AnalysisSnapshot
from app.models.signal_recommendation import SignalRecommendation
from app.models.ai_analysis_record import AIAnalysisRecord
from app.models.ai_generated_artifact import AIGeneratedArtifact
from app.models.backtest_task import BacktestTask
from app.models.backtest_trade import BacktestTrade
from app.models.execution_order import ExecutionOrder
from app.models.execution_fill import ExecutionFill
from app.models.system_log import SystemLog
from app.models.error_log import ErrorLog

__all__ = [
    "User", "ModuleConfig", "ExchangeConfig", "SymbolWatch",
    "MarketKline", "MarketTrade", "MarketOrderbookSnapshot",
    "MarketFunding", "MarketOpenInterest",
    "IndicatorDefinition", "FactorDefinition",
    "IndicatorResult", "FactorResult",
    "AnalysisSnapshot", "SignalRecommendation",
    "AIAnalysisRecord", "AIGeneratedArtifact",
    "BacktestTask", "BacktestTrade",
    "ExecutionOrder", "ExecutionFill",
    "SystemLog", "ErrorLog",
]

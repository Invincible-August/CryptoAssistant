"""
系统枚举定义模块。
定义所有业务相关的枚举类型。
"""
from enum import Enum


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"     # 管理员
    USER = "user"       # 普通用户


class MarketType(str, Enum):
    """市场类型枚举"""
    SPOT = "spot"       # 现货市场
    PERPETUAL = "perp"  # 永续合约市场


class OrderSide(str, Enum):
    """订单方向枚举"""
    BUY = "buy"         # 买入
    SELL = "sell"       # 卖出


class OrderType(str, Enum):
    """订单类型枚举"""
    LIMIT = "limit"     # 限价单
    MARKET = "market"   # 市价单


class OrderStatus(str, Enum):
    """订单状态枚举"""
    PENDING = "pending"       # 待处理
    PARTIAL = "partial"       # 部分成交
    FILLED = "filled"         # 完全成交
    CANCELLED = "cancelled"   # 已取消
    FAILED = "failed"         # 失败


class SignalDirection(str, Enum):
    """交易信号方向枚举"""
    LONG = "long"         # 做多
    SHORT = "short"       # 做空
    NEUTRAL = "neutral"   # 中性/观望


class SourceType(str, Enum):
    """数据来源枚举"""
    SYSTEM = "system"   # 系统自动生成
    HUMAN = "human"     # 人工输入
    AI = "ai"           # AI模型生成


class BacktestStatus(str, Enum):
    """回测任务状态枚举"""
    PENDING = "pending"       # 等待执行
    RUNNING = "running"       # 正在运行
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败


class ModuleName(str, Enum):
    """系统功能模块名称枚举"""
    AI = "ai"                             # AI助手模块
    TRADINGVIEW = "tradingview"           # TradingView信号接收模块
    EXECUTION = "execution"               # 自动下单执行模块
    BACKTEST = "backtest"                 # 策略回测模块
    EXCHANGE_BINANCE = "exchange_binance"  # Binance交易所对接模块


class KlineInterval(str, Enum):
    """K线时间周期枚举，值与Binance API参数对应"""
    MIN_1 = "1m"      # 1分钟
    MIN_3 = "3m"      # 3分钟
    MIN_5 = "5m"      # 5分钟
    MIN_15 = "15m"    # 15分钟
    MIN_30 = "30m"    # 30分钟
    HOUR_1 = "1h"     # 1小时
    HOUR_2 = "2h"     # 2小时
    HOUR_4 = "4h"     # 4小时
    HOUR_6 = "6h"     # 6小时
    HOUR_8 = "8h"     # 8小时
    HOUR_12 = "12h"   # 12小时
    DAY_1 = "1d"      # 1天
    WEEK_1 = "1w"     # 1周
    MONTH_1 = "1M"    # 1月


class WatchStatus(str, Enum):
    """监控任务状态枚举"""
    ACTIVE = "active"     # 监控中
    PAUSED = "paused"     # 已暂停
    STOPPED = "stopped"   # 已停止


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

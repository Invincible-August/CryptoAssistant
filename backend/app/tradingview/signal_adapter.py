"""
TradingView信号适配器模块。
将TradingView Alert解析后的信号格式转换为系统内部的
SignalRecommendation格式，实现外部信号源与内部交易流水线的对接。
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.enums import SignalDirection


# ==================== TV动作到系统方向的映射表 ====================
# TradingView的动作命名与系统内部的SignalDirection枚举存在差异，
# 需要通过映射表进行转换
_TV_ACTION_TO_DIRECTION: Dict[str, str] = {
    "buy": SignalDirection.LONG.value,       # 买入 → 做多
    "sell": SignalDirection.SHORT.value,      # 卖出 → 做空
    "close": SignalDirection.NEUTRAL.value,   # 平仓 → 中性（退出持仓）
}

# 默认的信号置信度——TradingView不提供置信度概念，
# 使用中等置信度作为基准，后续可由AI模块或评分引擎调整
_DEFAULT_CONFIDENCE = Decimal("0.6")

# 默认的信号胜率——同样TradingView不提供胜率，
# 使用保守估计，实际值应通过回测获得
_DEFAULT_WIN_RATE = Decimal("0.5")


def adapt_tv_signal_to_recommendation(
    tv_signal: Dict[str, Any],
    exchange: str = "binance",
    analysis_snapshot_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    将TradingView信号转换为系统内部的SignalRecommendation格式。

    转换逻辑：
    1. 将TV的 action（buy/sell/close）映射为系统的 direction（long/short/neutral）
    2. 将TV的 price 字符串转为 Decimal 精度价格
    3. 如果TV提供了止损/止盈，转换为系统格式
    4. 补充TV不提供的字段（置信度、胜率等）使用合理默认值
    5. 将策略名称和时间周期记录到 reasons_json 中

    Args:
        tv_signal: parse_webhook_payload() 返回的标准化TV信号字典
        exchange: 交易所标识，默认为 "binance"
        analysis_snapshot_id: 关联的分析快照ID（可选），
            如果信号同时触发了AI分析，可以关联到对应的快照

    Returns:
        Dict[str, Any]: 符合 SignalRecommendation 模型字段的字典，
            可直接用于创建 SignalRecommendation ORM实例
    """
    # ---- 解析交易方向 ----
    action = tv_signal.get("action", "").lower()
    direction = _TV_ACTION_TO_DIRECTION.get(action, SignalDirection.NEUTRAL.value)

    # ---- 解析交易对 ----
    symbol = tv_signal.get("symbol", "UNKNOWN").upper()

    # ---- 解析价格（安全转换，防止无效数字导致崩溃） ----
    trigger_price = _safe_decimal(tv_signal.get("price"))

    # ---- 构建入场区间：以触发价格为中心，上下浮动0.5%作为默认入场区间 ----
    entry_zone: Optional[Dict[str, Any]] = None
    if trigger_price is not None:
        # 0.5%的浮动范围——在高波动的加密货币市场中是相对合理的默认值
        zone_offset = trigger_price * Decimal("0.005")
        entry_zone = {
            "low": str(trigger_price - zone_offset),
            "high": str(trigger_price + zone_offset),
        }

    # ---- 解析止损价位 ----
    stop_loss = _safe_decimal(tv_signal.get("stop_loss"))

    # ---- 构建止盈列表 ----
    take_profits: List[Dict[str, Any]] = []
    tp_price = _safe_decimal(tv_signal.get("take_profit"))
    if tp_price is not None:
        # TradingView通常只提供单个止盈目标，放入列表中保持格式统一
        take_profits.append({
            "price": str(tp_price),
            "ratio": 1.0,  # 单一止盈时全仓出场
        })

    # ---- 构建推荐理由（记录信号来源和策略信息） ----
    reasons: List[str] = [f"TradingView信号触发（策略: {tv_signal.get('strategy', '未知')}）"]
    if tv_signal.get("timeframe"):
        reasons.append(f"时间周期: {tv_signal['timeframe']}")
    if tv_signal.get("comment"):
        reasons.append(f"备注: {tv_signal['comment']}")

    # ---- 构建风险提示 ----
    risks: List[str] = [
        "此信号来自TradingView外部Alert，未经系统内部多因子验证",
        "建议结合系统AI分析结果综合判断",
    ]
    # close动作的特殊风险提示
    if action == "close":
        risks.append("平仓信号不包含新开仓建议，仅表示退出当前持仓")

    # ---- 组装最终的SignalRecommendation字段 ----
    recommendation: Dict[str, Any] = {
        "exchange": exchange,
        "symbol": symbol,
        "direction": direction,
        "confidence": str(_DEFAULT_CONFIDENCE),
        "win_rate": str(_DEFAULT_WIN_RATE),
        "entry_zone": entry_zone,
        "stop_loss": str(stop_loss) if stop_loss is not None else None,
        "take_profits": take_profits if take_profits else None,
        "tp_strategy": None,
        "risks_json": risks,
        "reasons_json": reasons,
        "summary": _build_signal_summary(action, symbol, trigger_price, tv_signal),
    }

    # 关联分析快照（可选）
    if analysis_snapshot_id is not None:
        recommendation["analysis_snapshot_id"] = analysis_snapshot_id

    logger.info(
        f"TV信号适配完成: {symbol} {direction}, "
        f"价格={trigger_price}, 策略={tv_signal.get('strategy', 'N/A')}"
    )

    return recommendation


def adapt_batch_signals(
    tv_signals: List[Dict[str, Any]],
    exchange: str = "binance",
) -> List[Dict[str, Any]]:
    """
    批量转换TradingView信号为系统格式。

    遍历信号列表，逐一调用 adapt_tv_signal_to_recommendation，
    单条转换失败不影响其他信号的处理。

    Args:
        tv_signals: TradingView信号字典列表
        exchange: 交易所标识

    Returns:
        List[Dict[str, Any]]: 转换成功的SignalRecommendation字典列表
    """
    adapted_results: List[Dict[str, Any]] = []

    for idx, tv_signal in enumerate(tv_signals):
        try:
            recommendation = adapt_tv_signal_to_recommendation(
                tv_signal=tv_signal,
                exchange=exchange,
            )
            adapted_results.append(recommendation)
        except Exception as e:
            # 单条信号转换失败时记录错误并继续处理后续信号
            logger.error(f"第{idx}条TV信号适配失败: {e}")
            continue

    logger.info(f"批量适配完成: 总数={len(tv_signals)}, 成功={len(adapted_results)}")
    return adapted_results


def get_supported_actions() -> Dict[str, str]:
    """
    获取系统支持的TradingView动作到内部方向的映射表。

    供API接口文档或前端配置页面使用，
    让用户知道在TradingView Alert中应该填写什么action值。

    Returns:
        Dict[str, str]: 动作到方向的映射字典
    """
    return dict(_TV_ACTION_TO_DIRECTION)


# ==================== 内部工具函数 ====================


def _safe_decimal(value: Any) -> Optional[Decimal]:
    """
    安全地将值转换为Decimal类型。

    处理TradingView可能传来的各种格式：字符串数字、整数、浮点数、空字符串等。

    Args:
        value: 需要转换的值

    Returns:
        Optional[Decimal]: 转换成功返回Decimal，失败返回None
    """
    if value is None:
        return None

    str_value = str(value).strip()
    if not str_value:
        return None

    try:
        return Decimal(str_value)
    except InvalidOperation:
        logger.warning(f"无法将值转换为Decimal: '{value}'")
        return None


def _build_signal_summary(
    action: str,
    symbol: str,
    price: Optional[Decimal],
    tv_signal: Dict[str, Any],
) -> str:
    """
    构建信号摘要文本。

    将TV信号的关键信息组装成一句简洁的中文描述，
    用于SignalRecommendation的summary字段。

    Args:
        action: 交易动作
        symbol: 交易对名称
        price: 触发价格
        tv_signal: 原始TV信号数据

    Returns:
        str: 信号摘要文本
    """
    # 动作中文名映射
    action_names: Dict[str, str] = {
        "buy": "买入/做多",
        "sell": "卖出/做空",
        "close": "平仓",
    }
    action_name = action_names.get(action, action)

    # 基础摘要
    price_text = f"触发价格 {price}" if price else "价格未知"
    strategy_text = tv_signal.get("strategy", "")
    timeframe_text = tv_signal.get("timeframe", "")

    parts = [
        f"[TradingView信号] {symbol} {action_name}",
        price_text,
    ]
    if strategy_text:
        parts.append(f"策略: {strategy_text}")
    if timeframe_text:
        parts.append(f"周期: {timeframe_text}")

    return "，".join(parts)

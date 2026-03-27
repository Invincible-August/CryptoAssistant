"""
交易建议引擎模块。

职责：
1. 接收评分引擎和假设引擎的分析结果
2. 基于规则体系生成具体的交易建议
3. 输出完整的交易方案，包含方向、入场区间、止损、多级止盈、策略和风险提示

输出字段说明：
- direction:          交易方向 (long / short / neutral)
- entry_zone:         建议入场价格区间 [低位, 高位]
- win_rate:           基于历史统计的估算胜率
- stop_loss:          止损价格
- take_profits:       多级止盈目标列表
- tp_strategy:        止盈执行策略描述
- risk_warnings:      风险提示列表
- reasons:            做出该建议的核心理由列表
- position_size_pct:  建议仓位比例 (0-100%)
- confidence:         建议置信度 (0.0-1.0)

设计原则：
- 所有建议都是基于规则的（非AI预测），确保可解释性
- 保守优先：不确定时默认给出中性/观望建议
- 风险控制：止损永远比止盈先确定
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from loguru import logger


# ========== 方向判断阈值配置 ==========
# 这些阈值决定了在什么条件下系统会给出做多/做空/观望建议

# 做多所需的最低条件
LONG_ENTRY_THRESHOLDS: Dict[str, float] = {
    "min_control_strength": 55.0,        # 控盘强度不能太低（主力在操盘）
    "min_capital_reserve": 50.0,          # 资金余力不能耗尽
    "max_distribution_risk": 45.0,        # 派发风险不能太高
    "max_fake_move_risk": 55.0,           # 假动作风险需可控
}

# 做空所需的最低条件
SHORT_ENTRY_THRESHOLDS: Dict[str, float] = {
    "min_distribution_risk": 55.0,        # 派发风险较高（主力在出货）
    "max_control_strength": 50.0,         # 控盘强度下降（主力撤离）
    "max_capital_reserve": 50.0,          # 资金余力不足
}

# ========== 止损/止盈比例配置 ==========
# 根据波动率等级动态调整的比例范围

# 默认止损百分比（相对于入场价格）
DEFAULT_STOP_LOSS_PCT: float = 2.0

# 多级止盈目标的百分比倍数（相对于止损距离）
# 例如止损2%时：TP1=2%, TP2=4%, TP3=6%
TAKE_PROFIT_MULTIPLIERS: List[float] = [1.0, 2.0, 3.0]

# 各级止盈的建议平仓比例
TAKE_PROFIT_CLOSE_RATIOS: List[float] = [0.30, 0.40, 0.30]


def _determine_direction(
    scores: Dict[str, float],
    hypothesis: Dict[str, Any],
) -> str:
    """
    综合评分和假设引擎结果，确定交易方向。

    判断逻辑分三层：

    第一层：假设引擎的 action_bias 提供初步方向
    第二层：评分阈值做"硬性门槛"过滤
    第三层：矛盾信号降级为观望

    Args:
        scores:     五维评分结果
        hypothesis: 假设引擎输出的完整报告

    Returns:
        str: "long" / "short" / "neutral"
    """
    # 从假设引擎获取行动偏向
    action_bias = hypothesis.get("action_bias", "neutral")

    control = scores.get("control_strength_score", 50.0)
    reserve = scores.get("capital_reserve_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)
    fake_move = scores.get("fake_move_risk_score", 50.0)

    # ===== 做多方向判断 =====
    if action_bias == "bullish":
        # 检查做多的硬性条件
        conditions_met = (
            control >= LONG_ENTRY_THRESHOLDS["min_control_strength"]
            and reserve >= LONG_ENTRY_THRESHOLDS["min_capital_reserve"]
            and distribution <= LONG_ENTRY_THRESHOLDS["max_distribution_risk"]
            and fake_move <= LONG_ENTRY_THRESHOLDS["max_fake_move_risk"]
        )

        if conditions_met:
            return "long"
        else:
            # 条件不全满足，降级为观望
            logger.info("做多偏向但部分条件未满足，降级为 neutral")
            return "neutral"

    # ===== 做空方向判断 =====
    elif action_bias == "bearish":
        conditions_met = (
            distribution >= SHORT_ENTRY_THRESHOLDS["min_distribution_risk"]
            and control <= SHORT_ENTRY_THRESHOLDS["max_control_strength"]
            and reserve <= SHORT_ENTRY_THRESHOLDS["max_capital_reserve"]
        )

        if conditions_met:
            return "short"
        else:
            logger.info("做空偏向但部分条件未满足，降级为 neutral")
            return "neutral"

    # ===== 其他情况（cautious / neutral）=====
    return "neutral"


def _estimate_win_rate(
    scores: Dict[str, float],
    direction: str,
    confidence: float,
) -> float:
    """
    估算交易的胜率。

    胜率估算基于以下因素：
    1. 假设引擎的置信度（基础值）
    2. 关键维度的评分强度（调整项）
    3. 风险维度的影响（扣减项）

    这不是精确的统计胜率，而是基于当前信号强度的定性估算。

    Args:
        scores:     五维评分
        direction:  交易方向
        confidence: 假设引擎的阶段置信度

    Returns:
        float: 估算胜率 (0.0 ~ 1.0)
    """
    if direction == "neutral":
        # 中性方向没有交易，胜率无意义
        return 0.0

    # 基础胜率：来自假设引擎的置信度
    # 置信度越高说明市场信号越一致，胜率基础越高
    base_win_rate = confidence * 0.5  # 置信度1.0时基础胜率50%

    control = scores.get("control_strength_score", 50.0)
    reserve = scores.get("capital_reserve_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)
    fake_move = scores.get("fake_move_risk_score", 50.0)

    adjustment = 0.0

    if direction == "long":
        # 做多时：控盘强度和资金余力是加分项
        adjustment += (control - 50) / 100 * 0.15    # 控盘70 → +3%
        adjustment += (reserve - 50) / 100 * 0.10    # 余力70 → +2%
        # 派发风险和假动作风险是减分项
        adjustment -= (distribution - 30) / 100 * 0.10
        adjustment -= (fake_move - 30) / 100 * 0.08

    elif direction == "short":
        # 做空时：派发风险是加分项
        adjustment += (distribution - 50) / 100 * 0.15
        # 控盘强度是减分项（控盘强说明主力还在，做空危险）
        adjustment -= (control - 40) / 100 * 0.12

    # 合成最终胜率并限制在合理范围 [0.15, 0.85]
    final_win_rate = base_win_rate + adjustment
    final_win_rate = max(0.15, min(0.85, final_win_rate))

    return round(final_win_rate, 3)


def _calculate_entry_zone(
    current_price: float,
    direction: str,
    scores: Dict[str, float],
) -> List[float]:
    """
    计算建议的入场价格区间。

    入场区间不是当前价格，而是一个"更优入场"的区间——
    等价格回到这个区间再入场，可以获得更好的风险收益比。

    区间宽度与波动性相关（通过评分间接反映）。

    做多时：入场区间在当前价格下方（等回调）
    做空时：入场区间在当前价格上方（等反弹）

    Args:
        current_price: 当前市场价格
        direction:     交易方向
        scores:        五维评分

    Returns:
        List[float]: [区间下界, 区间上界]
    """
    if direction == "neutral" or current_price <= 0:
        return [0.0, 0.0]

    fake_move = scores.get("fake_move_risk_score", 50.0)

    # 假动作风险越高，建议等更深的回调/反弹再入场
    # 基础回调幅度 0.5%~1.5%，假动作风险每增加10分多等0.2%
    base_offset_pct = 0.5 + (fake_move - 30) / 100 * 2.0
    base_offset_pct = max(0.3, min(3.0, base_offset_pct))

    # 区间宽度：占回调幅度的 60%
    zone_width_pct = base_offset_pct * 0.6

    if direction == "long":
        # 做多：入场区间在当前价格下方
        zone_upper = current_price * (1 - base_offset_pct / 100)
        zone_lower = current_price * (1 - (base_offset_pct + zone_width_pct) / 100)
    else:
        # 做空：入场区间在当前价格上方
        zone_lower = current_price * (1 + base_offset_pct / 100)
        zone_upper = current_price * (1 + (base_offset_pct + zone_width_pct) / 100)

    return [round(zone_lower, 6), round(zone_upper, 6)]


def _calculate_stop_loss(
    entry_zone: List[float],
    direction: str,
    scores: Dict[str, float],
) -> float:
    """
    计算止损价格。

    止损位置基于入场区间和波动性动态调整。
    核心原则：止损必须放在关键支撑/阻力之外，
    同时又不能离入场价太远导致风险收益比失衡。

    做多时：止损在入场区间下方
    做空时：止损在入场区间上方

    Args:
        entry_zone: 入场区间 [下界, 上界]
        direction:  交易方向
        scores:     五维评分

    Returns:
        float: 止损价格
    """
    if direction == "neutral" or entry_zone == [0.0, 0.0]:
        return 0.0

    fake_move = scores.get("fake_move_risk_score", 50.0)

    # 假动作风险越高，止损要放更远——防止被假突破/假跌破扫掉
    stop_loss_pct = DEFAULT_STOP_LOSS_PCT + (fake_move - 40) / 100 * 2.0
    stop_loss_pct = max(1.0, min(5.0, stop_loss_pct))

    if direction == "long":
        # 做多止损：从入场区间下界再往下放
        reference_price = entry_zone[0]  # 取入场区间下界作为参考
        stop_loss_price = reference_price * (1 - stop_loss_pct / 100)
    else:
        # 做空止损：从入场区间上界再往上放
        reference_price = entry_zone[1]
        stop_loss_price = reference_price * (1 + stop_loss_pct / 100)

    return round(stop_loss_price, 6)


def _calculate_take_profits(
    entry_zone: List[float],
    stop_loss: float,
    direction: str,
) -> List[Dict[str, Any]]:
    """
    计算多级止盈目标。

    止盈采用多级递进策略：
    - TP1（保守目标）：风险收益比 1:1，到达后平仓30%
    - TP2（标准目标）：风险收益比 1:2，到达后平仓40%
    - TP3（激进目标）：风险收益比 1:3，到达后平仓剩余30%

    多级止盈的优势：
    1. TP1 快速回收部分利润，降低心理压力
    2. TP2 锁定主要利润
    3. TP3 保留追踪大行情的可能性

    Args:
        entry_zone: 入场区间
        stop_loss:  止损价格
        direction:  交易方向

    Returns:
        List[Dict[str, Any]]: 止盈目标列表，每项包含：
            - level: 止盈级别 (TP1/TP2/TP3)
            - price: 目标价格
            - close_ratio: 该级别平仓比例
            - rr_ratio: 风险收益比
    """
    if direction == "neutral":
        return []

    # 计算入场参考价（使用入场区间中位数）
    entry_mid = (entry_zone[0] + entry_zone[1]) / 2

    # 止损距离 = 入场中位数到止损的绝对距离
    stop_distance = abs(entry_mid - stop_loss)

    if stop_distance <= 0:
        logger.warning("止损距离为0，无法计算止盈目标")
        return []

    take_profit_targets: List[Dict[str, Any]] = []

    for i, (multiplier, close_ratio) in enumerate(
        zip(TAKE_PROFIT_MULTIPLIERS, TAKE_PROFIT_CLOSE_RATIOS)
    ):
        # 止盈距离 = 止损距离 × 倍数
        tp_distance = stop_distance * multiplier

        if direction == "long":
            # 做多止盈：入场价格 + 止盈距离
            tp_price = entry_mid + tp_distance
        else:
            # 做空止盈：入场价格 - 止盈距离
            tp_price = entry_mid - tp_distance

        take_profit_targets.append({
            "level": f"TP{i + 1}",
            "price": round(tp_price, 6),
            "close_ratio": close_ratio,
            "rr_ratio": f"1:{multiplier:.0f}",
        })

    return take_profit_targets


def _generate_tp_strategy(
    direction: str,
    take_profits: List[Dict[str, Any]],
) -> str:
    """
    生成止盈执行策略的文字描述。

    根据交易方向和多级止盈目标，生成一段清晰的止盈执行方案文字，
    帮助交易者理解何时该平多少仓位。

    Args:
        direction:    交易方向
        take_profits: 多级止盈目标列表

    Returns:
        str: 止盈策略描述文本
    """
    if direction == "neutral" or not take_profits:
        return "当前为观望状态，无止盈策略。"

    direction_text = "做多" if direction == "long" else "做空"

    strategy_parts: List[str] = [
        f"【{direction_text}止盈策略 — 分批平仓】"
    ]

    for tp in take_profits:
        close_pct = int(tp["close_ratio"] * 100)
        strategy_parts.append(
            f"  {tp['level']}: 价格到达 {tp['price']} 时平仓 {close_pct}% 仓位"
            f"（风险收益比 {tp['rr_ratio']}）"
        )

    strategy_parts.append(
        "  ※ 当 TP1 触发后，将止损移动到入场价（保本止损），"
        "消除剩余仓位的亏损风险。"
    )

    return "\n".join(strategy_parts)


def _determine_position_size(
    scores: Dict[str, float],
    direction: str,
    confidence: float,
) -> float:
    """
    计算建议的仓位比例（占总资金的百分比）。

    仓位大小取决于：
    1. 信号一致性（置信度越高 → 仓位越大）
    2. 风险水平（派发风险/假动作风险越高 → 仓位越小）
    3. 资金余力（主力余力越足 → 行情延续性越好 → 可适当加仓）

    基础原则：
    - 单笔最大仓位不超过总资金的 15%
    - 不确定时仓位不超过 5%
    - 强信号时可到 10-15%

    Args:
        scores:     五维评分
        direction:  交易方向
        confidence: 假设引擎置信度

    Returns:
        float: 建议仓位百分比 (0.0 ~ 15.0)
    """
    if direction == "neutral":
        return 0.0

    # 基础仓位 = 置信度 × 最大仓位
    max_position = 15.0
    base_position = confidence * max_position  # 置信度0.8 → 基础仓位12%

    fake_move = scores.get("fake_move_risk_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)

    # 风险调整：假动作风险和派发风险越高，仓位越要缩减
    risk_penalty = 0.0
    if fake_move >= 50:
        # 假动作风险每高出50分10%，减少仓位10%
        risk_penalty += (fake_move - 50) / 100 * max_position * 0.3
    if distribution >= 50 and direction == "long":
        # 做多时派发风险高要额外减仓
        risk_penalty += (distribution - 50) / 100 * max_position * 0.2

    final_position = max(1.0, base_position - risk_penalty)
    final_position = min(max_position, final_position)

    return round(final_position, 1)


def _build_reasons(
    scores: Dict[str, float],
    hypothesis: Dict[str, Any],
    direction: str,
) -> List[str]:
    """
    构建做出该交易建议的核心理由列表。

    理由应当清晰、具体，便于交易者理解系统的决策依据。

    Args:
        scores:     五维评分
        hypothesis: 假设引擎报告
        direction:  交易方向

    Returns:
        List[str]: 核心理由列表
    """
    reasons: List[str] = []

    stage = hypothesis.get("market_stage", {}).get("stage_key", "uncertain")
    stage_name = hypothesis.get("market_stage", {}).get("stage_name", "未知")
    confidence = hypothesis.get("market_stage", {}).get("confidence", 0.0)

    control = scores.get("control_strength_score", 50.0)
    reserve = scores.get("capital_reserve_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)
    follow = scores.get("follow_score", 50.0)
    fake_move = scores.get("fake_move_risk_score", 50.0)

    # 阶段判断理由
    reasons.append(
        f"行为假设引擎判断当前为【{stage_name}】阶段，置信度 {confidence:.0%}"
    )

    if direction == "long":
        # 做多理由
        if control >= 60:
            reasons.append(f"主力控盘迹象明显（控盘强度: {control:.0f}/100）")
        if reserve >= 60:
            reasons.append(f"资金余力充裕，行情有延续空间（资金余力: {reserve:.0f}/100）")
        if distribution <= 35:
            reasons.append(f"派发风险处于低位（{distribution:.0f}/100），尚无出货信号")
        if stage == "spring":
            reasons.append("出现弹簧效应（Spring），假跌破后的快速拉回是经典吸筹信号")
        if stage == "accumulation":
            reasons.append("处于吸筹阶段，主力正在低位建仓，是潜在的中长期入场点")

    elif direction == "short":
        if distribution >= 60:
            reasons.append(f"派发风险信号密集（{distribution:.0f}/100），多个出货指标共振")
        if reserve <= 40:
            reasons.append(f"资金余力不足（{reserve:.0f}/100），行情难以延续")
        if control <= 40:
            reasons.append(f"控盘迹象消退（{control:.0f}/100），主力可能已撤离")
        if stage == "upthrust":
            reasons.append("出现上冲回落（Upthrust），假突破后回落是典型的出货信号")
        if stage == "distribution":
            reasons.append("处于派发阶段，主力正在高位出货，价格下行概率增大")

    else:
        # 中性/观望理由
        reasons.append("各维度信号未形成一致方向，不满足入场条件")
        if fake_move >= 55:
            reasons.append(f"假动作风险偏高（{fake_move:.0f}/100），突破信号可信度不足")
        if 40 <= distribution <= 60:
            reasons.append(f"派发风险处于模糊区间（{distribution:.0f}/100），方向不明")

    return reasons


def _build_risk_warnings(
    scores: Dict[str, float],
    hypothesis: Dict[str, Any],
    direction: str,
) -> List[str]:
    """
    构建交易风险提示列表。

    风险提示帮助交易者了解该笔交易可能失败的场景。

    Args:
        scores:     五维评分
        hypothesis: 假设引擎报告
        direction:  交易方向

    Returns:
        List[str]: 风险提示列表
    """
    warnings: List[str] = []

    fake_move = scores.get("fake_move_risk_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)
    follow = scores.get("follow_score", 50.0)
    control = scores.get("control_strength_score", 50.0)

    if direction == "neutral":
        warnings.append("当前不建议入场，请等待更明确的信号")
        return warnings

    # 通用风险
    if fake_move >= 50:
        warnings.append(
            f"假动作风险偏高（{fake_move:.0f}/100），"
            "需警惕止损被虚假行情触发"
        )

    if follow >= 65:
        warnings.append(
            f"散户情绪过热（跟风度: {follow:.0f}/100），"
            "市场可能出现剧烈反转"
        )

    # 做多特定风险
    if direction == "long":
        if distribution >= 40:
            warnings.append(
                f"派发风险不低（{distribution:.0f}/100），"
                "需密切关注量价背离信号"
            )
        warnings.append("重大利空消息或黑天鹅事件可能导致行情急跌")

    # 做空特定风险
    elif direction == "short":
        if control >= 55:
            warnings.append(
                f"主力仍有控盘迹象（{control:.0f}/100），"
                "逼空风险不可忽视"
            )
        warnings.append("正向资金费率过高时做空需承担费率成本")

    # 补充系统性风险提示
    warnings.append("以上分析仅基于量化指标推断，不构成投资建议，请独立判断")

    return warnings


class RecommendationEngine:
    """
    交易建议引擎。

    作为分析链路的最末端，将评分引擎和假设引擎的分析结果
    转化为具体的、可执行的交易建议方案。

    核心输出包含：
    - 交易方向（做多/做空/观望）
    - 入场价格区间
    - 止损位置
    - 多级止盈目标
    - 止盈执行策略
    - 仓位建议
    - 决策理由
    - 风险提示

    Attributes:
        _default_stop_loss_pct: 默认止损百分比
        _max_position_pct:     单笔最大仓位比例
    """

    def __init__(self) -> None:
        """初始化交易建议引擎。"""
        self._default_stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT
        self._max_position_pct: float = 15.0

    def generate_recommendation(
        self,
        scores: Dict[str, float],
        hypothesis: Dict[str, Any],
        current_price: float,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        """
        生成完整的交易建议。

        这是建议引擎的主入口方法，按以下步骤执行：

        1. 确定交易方向：综合评分阈值和假设引擎偏向
        2. 计算入场区间：基于当前价格和波动性
        3. 设定止损位置：风险优先，确保可控
        4. 计算多级止盈：风险收益比递进，分批获利
        5. 生成止盈策略：文字描述执行方案
        6. 估算胜率：基于信号强度的定性估算
        7. 确定仓位：置信度和风险的综合权衡
        8. 构建理由和风险提示

        Args:
            scores:        评分引擎输出的五维评分
            hypothesis:    假设引擎输出的行为假设报告
            current_price: 当前市场价格
            symbol:        交易对名称，如 "BTCUSDT"

        Returns:
            Dict[str, Any]: 完整交易建议，结构如下：
            {
                "timestamp":        ISO格式时间戳,
                "symbol":           交易对名称,
                "current_price":    当前价格,
                "direction":        "long" / "short" / "neutral",
                "entry_zone":       [下界, 上界],
                "stop_loss":        止损价格,
                "take_profits":     多级止盈列表,
                "tp_strategy":      止盈策略描述,
                "win_rate":         估算胜率,
                "position_size_pct": 建议仓位百分比,
                "confidence":       建议置信度,
                "risk_warnings":    风险提示列表,
                "reasons":          决策理由列表,
                "market_stage":     市场阶段信息,
                "scores_snapshot":  原始评分快照,
            }
        """
        logger.info(f"========== 开始生成交易建议: {symbol} ==========")

        # 提取假设引擎的置信度
        hypothesis_confidence = hypothesis.get(
            "market_stage", {}
        ).get("confidence", 0.5)

        # 第一步：确定交易方向
        direction = _determine_direction(scores, hypothesis)
        logger.info(f"交易方向判断: {direction}")

        # 第二步：计算入场区间
        entry_zone = _calculate_entry_zone(current_price, direction, scores)
        logger.info(f"建议入场区间: {entry_zone}")

        # 第三步：设定止损价格
        stop_loss = _calculate_stop_loss(entry_zone, direction, scores)
        logger.info(f"止损价格: {stop_loss}")

        # 第四步：计算多级止盈目标
        take_profits = _calculate_take_profits(entry_zone, stop_loss, direction)

        # 第五步：生成止盈策略描述
        tp_strategy = _generate_tp_strategy(direction, take_profits)

        # 第六步：估算胜率
        win_rate = _estimate_win_rate(scores, direction, hypothesis_confidence)
        logger.info(f"估算胜率: {win_rate:.1%}")

        # 第七步：确定仓位大小
        position_size = _determine_position_size(scores, direction, hypothesis_confidence)
        logger.info(f"建议仓位: {position_size}%")

        # 第八步：构建理由和风险提示
        reasons = _build_reasons(scores, hypothesis, direction)
        risk_warnings = _build_risk_warnings(scores, hypothesis, direction)

        # 组装完整建议
        recommendation: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "current_price": current_price,
            "direction": direction,
            "entry_zone": entry_zone,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "tp_strategy": tp_strategy,
            "win_rate": win_rate,
            "position_size_pct": position_size,
            "confidence": hypothesis_confidence,
            "risk_warnings": risk_warnings,
            "reasons": reasons,
            "market_stage": hypothesis.get("market_stage", {}),
            "scores_snapshot": scores,
        }

        logger.info(
            f"交易建议生成完成: {symbol} | "
            f"方向={direction} | "
            f"胜率={win_rate:.1%} | "
            f"仓位={position_size}%"
        )

        return recommendation

    def format_recommendation_text(
        self,
        recommendation: Dict[str, Any],
    ) -> str:
        """
        将交易建议格式化为人类可读的文本报告。

        适用于发送到终端、日志、消息推送等纯文本场景。

        Args:
            recommendation: generate_recommendation 的输出

        Returns:
            str: 格式化的文本报告
        """
        symbol = recommendation.get("symbol", "UNKNOWN")
        direction = recommendation.get("direction", "neutral")
        current_price = recommendation.get("current_price", 0)
        entry_zone = recommendation.get("entry_zone", [0, 0])
        stop_loss = recommendation.get("stop_loss", 0)
        take_profits = recommendation.get("take_profits", [])
        win_rate = recommendation.get("win_rate", 0)
        position_size = recommendation.get("position_size_pct", 0)
        confidence = recommendation.get("confidence", 0)
        reasons = recommendation.get("reasons", [])
        risk_warnings = recommendation.get("risk_warnings", [])
        stage_name = recommendation.get("market_stage", {}).get("stage_name", "未知")
        tp_strategy = recommendation.get("tp_strategy", "")

        # 方向中文映射
        direction_text_map = {
            "long": "📈 做多 (Long)",
            "short": "📉 做空 (Short)",
            "neutral": "⏸ 观望 (Neutral)",
        }
        direction_text = direction_text_map.get(direction, "未知")

        lines: List[str] = [
            f"{'=' * 50}",
            f"  交易建议报告 — {symbol}",
            f"{'=' * 50}",
            f"",
            f"当前价格:   {current_price}",
            f"市场阶段:   {stage_name}",
            f"交易方向:   {direction_text}",
            f"置信度:     {confidence:.0%}",
            f"估算胜率:   {win_rate:.1%}",
            f"建议仓位:   {position_size}%",
            f"",
        ]

        if direction != "neutral":
            lines.extend([
                f"--- 入场与出场 ---",
                f"入场区间:   {entry_zone[0]} ~ {entry_zone[1]}",
                f"止损价格:   {stop_loss}",
                f"",
            ])

            if take_profits:
                lines.append("止盈目标:")
                for tp in take_profits:
                    close_pct = int(tp["close_ratio"] * 100)
                    lines.append(
                        f"  {tp['level']}: {tp['price']} "
                        f"(平仓 {close_pct}%, RR {tp['rr_ratio']})"
                    )
                lines.append("")

            if tp_strategy:
                lines.append("止盈策略:")
                lines.append(tp_strategy)
                lines.append("")

        lines.append("--- 决策理由 ---")
        for i, reason in enumerate(reasons, 1):
            lines.append(f"  {i}. {reason}")
        lines.append("")

        lines.append("--- 风险提示 ---")
        for i, warning in enumerate(risk_warnings, 1):
            lines.append(f"  {i}. {warning}")

        lines.extend([
            f"",
            f"{'=' * 50}",
            f"  ※ 以上分析仅供参考，不构成投资建议",
            f"{'=' * 50}",
        ])

        return "\n".join(lines)

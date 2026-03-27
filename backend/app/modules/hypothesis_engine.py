"""
主导资金行为推断模块（行为假设引擎）。

职责：
1. 接收评分引擎输出的五维评分结果
2. 基于评分组合和阈值规则，推断当前市场所处的阶段
3. 生成结构化的行为假设，包含假设描述、支撑证据和潜在风险
4. 输出可供交易建议引擎直接消费的结构化 JSON

核心概念 —— 威科夫市场周期（Wyckoff Market Cycle）：
- 吸筹阶段 (Accumulation):  主力在低位静默建仓，价格横盘，量缩
- 拉升阶段 (Markup):         主力开始推升价格，量价齐升
- 派发阶段 (Distribution):   主力在高位出货，价格高位震荡
- 下跌阶段 (Markdown):       主力出货完毕，价格开始下跌
- 二次测试 (Re-test):        关键位置的回踩确认
- 弹簧效应 (Spring):         假跌破后快速拉回，典型吸筹手法
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from loguru import logger


# ========== 市场阶段定义 ==========
# 每个阶段的中英文名称和简述
MARKET_STAGES: Dict[str, Dict[str, str]] = {
    "accumulation": {
        "name": "吸筹阶段",
        "description": "主力在低位区间静默吸纳筹码，市场表现为窄幅横盘、成交萎缩、散户失去兴趣",
    },
    "markup": {
        "name": "拉升阶段",
        "description": "主力开始推升价格，量价配合良好，趋势性上涨，散户开始注意并跟进",
    },
    "distribution": {
        "name": "派发阶段",
        "description": "主力在高位将筹码转移给散户，表现为高位放量震荡、频繁插针、利好频出但涨不动",
    },
    "markdown": {
        "name": "下跌阶段",
        "description": "主力出货完毕，价格失去支撑开始下跌，量能放大伴随恐慌抛售",
    },
    "re_accumulation": {
        "name": "再吸筹阶段",
        "description": "上涨途中的中继整理，主力在更高的位置继续建仓，为下一波拉升做准备",
    },
    "re_distribution": {
        "name": "再派发阶段",
        "description": "下跌途中的中继反弹，主力在较高位置继续出货，准备更深一轮的下跌",
    },
    "spring": {
        "name": "弹簧效应",
        "description": "假跌破支撑后迅速拉回，主力借止损猎杀吸纳低价筹码的典型手法",
    },
    "upthrust": {
        "name": "上冲回落",
        "description": "假突破阻力后迅速回落，主力借突破诱多出货的典型手法",
    },
    "uncertain": {
        "name": "不确定阶段",
        "description": "各项指标信号矛盾，无法做出明确的阶段判断，建议观望等待更多信号",
    },
}


def _determine_market_stage(scores: Dict[str, float]) -> str:
    """
    根据五维评分组合判断当前市场所处的阶段。

    判断逻辑基于威科夫周期理论，通过评分组合的特征匹配来推断阶段：

    吸筹阶段特征：
    - 控盘强度高（主力在操作）+ 派发风险低（不是在出货）
    - 跟风度低（散户不关注）+ 资金余力充足

    拉升阶段特征：
    - 控盘强度高 + 资金余力高（有能力继续推升）
    - 跟风度中高（散户开始关注）+ 派发风险低

    派发阶段特征：
    - 派发风险高 + 跟风度高（散户大量涌入接盘）
    - 资金余力下降 + 假动作风险高

    下跌阶段特征：
    - 控盘强度低（主力已撤离）+ 资金余力低
    - 派发风险高（仍在出货）+ 跟风度下降（散户开始恐慌）

    Args:
        scores: 评分引擎输出的五维评分

    Returns:
        str: 市场阶段标识符（对应 MARKET_STAGES 的 key）
    """
    control = scores.get("control_strength_score", 50.0)
    reserve = scores.get("capital_reserve_score", 50.0)
    follow = scores.get("follow_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)
    fake_move = scores.get("fake_move_risk_score", 50.0)

    # ===== 弹簧效应（Spring）=====
    # 假跌破 + 高控盘 + 低派发 → 主力借假跌破吸筹
    if fake_move >= 70 and control >= 60 and distribution <= 35:
        return "spring"

    # ===== 上冲回落（Upthrust）=====
    # 假突破 + 高派发 + 跟风度高 → 主力借假突破出货
    if fake_move >= 70 and distribution >= 60 and follow >= 60:
        return "upthrust"

    # ===== 吸筹阶段 =====
    # 高控盘 + 充裕资金 + 低派发 + 低跟风（散户不关注）
    if control >= 60 and reserve >= 55 and distribution <= 40 and follow <= 40:
        return "accumulation"

    # ===== 拉升阶段 =====
    # 高控盘 + 充裕资金 + 低派发 + 中等以上跟风（散户开始跟进）
    if control >= 55 and reserve >= 55 and distribution <= 45 and follow > 40:
        return "markup"

    # ===== 派发阶段 =====
    # 高派发 + 高跟风（散户大量接盘）+ 资金余力下降
    if distribution >= 60 and follow >= 55 and reserve <= 50:
        return "distribution"

    # ===== 再派发阶段 =====
    # 派发信号中等 + 控盘下降 + 假动作风险高
    if distribution >= 50 and control <= 45 and fake_move >= 55:
        return "re_distribution"

    # ===== 下跌阶段 =====
    # 低控盘 + 低资金 + 高派发
    if control <= 40 and reserve <= 40 and distribution >= 50:
        return "markdown"

    # ===== 再吸筹阶段 =====
    # 中高控盘 + 中等资金 + 中等跟风 + 低派发
    if control >= 50 and reserve >= 45 and follow >= 35 and distribution <= 45:
        return "re_accumulation"

    # ===== 无法判断 =====
    return "uncertain"


def _build_evidence_list(
    scores: Dict[str, float],
    stage: str,
) -> List[Dict[str, Any]]:
    """
    根据评分和阶段判断结果，构建支撑证据列表。

    每条证据包含：
    - factor: 相关因子/维度名称
    - signal: 信号描述（中文）
    - strength: 信号强度（strong / moderate / weak）
    - score: 对应的原始评分值

    Args:
        scores: 五维评分结果
        stage:  已判断的市场阶段

    Returns:
        List[Dict[str, Any]]: 支撑证据列表
    """
    evidence_list: List[Dict[str, Any]] = []

    control = scores.get("control_strength_score", 50.0)
    reserve = scores.get("capital_reserve_score", 50.0)
    follow = scores.get("follow_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)
    fake_move = scores.get("fake_move_risk_score", 50.0)

    # ===== 控盘强度相关证据 =====
    if control >= 70:
        evidence_list.append({
            "factor": "控盘强度",
            "signal": "主力控盘迹象极为明显，成交分布集中、价格走势受控",
            "strength": "strong",
            "score": control,
        })
    elif control >= 55:
        evidence_list.append({
            "factor": "控盘强度",
            "signal": "存在一定的控盘迹象，价格走势相对有序",
            "strength": "moderate",
            "score": control,
        })
    elif control <= 35:
        evidence_list.append({
            "factor": "控盘强度",
            "signal": "控盘迹象薄弱，市场可能处于无序状态或主力已撤离",
            "strength": "strong",
            "score": control,
        })

    # ===== 资金余力相关证据 =====
    if reserve >= 70:
        evidence_list.append({
            "factor": "资金余力",
            "signal": "资金充裕，持仓量增长、费率适中，行情有继续推进的能力",
            "strength": "strong",
            "score": reserve,
        })
    elif reserve <= 35:
        evidence_list.append({
            "factor": "资金余力",
            "signal": "资金面紧张，持仓减少或费率极端，行情延续能力不足",
            "strength": "strong",
            "score": reserve,
        })

    # ===== 跟风可利用度相关证据 =====
    if follow >= 70:
        evidence_list.append({
            "factor": "跟风可利用度",
            "signal": "散户情绪极度一致，FOMO明显，容易被主力反向利用",
            "strength": "strong",
            "score": follow,
        })
    elif follow >= 55:
        evidence_list.append({
            "factor": "跟风可利用度",
            "signal": "散户有一定跟风行为，多空比例出现偏斜",
            "strength": "moderate",
            "score": follow,
        })

    # ===== 派发风险相关证据 =====
    if distribution >= 70:
        evidence_list.append({
            "factor": "派发风险",
            "signal": "多个派发信号共振：量价背离、卖压增大、动量衰竭",
            "strength": "strong",
            "score": distribution,
        })
    elif distribution >= 50:
        evidence_list.append({
            "factor": "派发风险",
            "signal": "出现部分派发信号，需关注后续量价配合",
            "strength": "moderate",
            "score": distribution,
        })

    # ===== 假动作风险相关证据 =====
    if fake_move >= 70:
        evidence_list.append({
            "factor": "假动作风险",
            "signal": "假突破/假跌破概率高，缺乏量能确认，疑似止损猎杀",
            "strength": "strong",
            "score": fake_move,
        })
    elif fake_move >= 50:
        evidence_list.append({
            "factor": "假动作风险",
            "signal": "存在假动作可能，突破的量能确认不够充分",
            "strength": "moderate",
            "score": fake_move,
        })

    return evidence_list


def _build_risk_list(
    scores: Dict[str, float],
    stage: str,
) -> List[str]:
    """
    根据评分和市场阶段，生成潜在风险提示列表。

    风险提示帮助交易者识别当前判断中的不确定性和需要警惕的场景。

    Args:
        scores: 五维评分结果
        stage:  已判断的市场阶段

    Returns:
        List[str]: 风险提示字符串列表
    """
    risk_warnings: List[str] = []

    control = scores.get("control_strength_score", 50.0)
    reserve = scores.get("capital_reserve_score", 50.0)
    follow = scores.get("follow_score", 50.0)
    distribution = scores.get("distribution_risk_score", 50.0)
    fake_move = scores.get("fake_move_risk_score", 50.0)

    # 通用风险：评分矛盾
    if control >= 60 and distribution >= 60:
        risk_warnings.append(
            "⚠ 控盘强度和派发风险同时偏高，信号矛盾——"
            "可能处于派发阶段末期，主力仍在操盘但已开始出货"
        )

    # 阶段特定风险
    if stage == "accumulation":
        risk_warnings.append(
            "吸筹阶段可能持续较长时间，过早入场面临时间成本风险"
        )
        if fake_move >= 50:
            risk_warnings.append(
                "存在假跌破风险，可能出现最后一轮洗盘"
            )

    elif stage == "markup":
        if reserve <= 50:
            risk_warnings.append(
                "资金余力不足，拉升可能即将结束，注意冲高回落风险"
            )
        if follow >= 70:
            risk_warnings.append(
                "散户跟风情绪过热，主力可能借机进入派发阶段"
            )

    elif stage == "distribution":
        risk_warnings.append(
            "派发阶段做多风险极高，任何反弹都可能是出货机会"
        )
        if control >= 55:
            risk_warnings.append(
                "主力仍有一定控盘力，可能制造假突破诱多后继续出货"
            )

    elif stage == "markdown":
        risk_warnings.append(
            "下跌趋势中抄底风险极高，需等待明确的止跌信号"
        )
        if fake_move >= 50:
            risk_warnings.append(
                "反弹可能是假动作，不宜轻易做多"
            )

    elif stage in ("spring", "upthrust"):
        risk_warnings.append(
            "假动作判断有一定概率失误，建议等待价格回到关键区域确认后再行动"
        )

    elif stage == "uncertain":
        risk_warnings.append(
            "各维度信号矛盾，无法形成一致性判断，建议保持观望"
        )
        risk_warnings.append(
            "避免在信号不明确时进行方向性下注"
        )

    # 通用风险补充
    if fake_move >= 65:
        risk_warnings.append(
            "假动作风险较高，所有突破/跌破信号需要额外的量能确认"
        )

    if follow >= 75:
        risk_warnings.append(
            "散户情绪过于极端，市场可能出现剧烈反转"
        )

    return risk_warnings


class HypothesisEngine:
    """
    主导资金行为推断引擎。

    基于评分引擎的多维度评分结果，推断当前市场所处的阶段，
    并生成结构化的行为假设。

    输出是一个完整的 JSON 结构，包含：
    - 市场阶段判断及置信度
    - 主力行为假设描述
    - 支撑证据列表
    - 潜在风险提示
    - 行动建议方向

    这个模块是连接"数据分析"和"交易决策"的桥梁——
    它将冰冷的评分数字转化为可理解的市场行为叙事。
    """

    def __init__(self) -> None:
        """初始化行为假设引擎。"""
        pass

    def _calculate_confidence(
        self,
        scores: Dict[str, float],
        stage: str,
    ) -> float:
        """
        计算阶段判断的置信度。

        置信度越高，说明各维度评分对该阶段判断的支撑越一致。

        计算方法：
        1. 根据不同阶段定义"理想评分模式"
        2. 计算实际评分与理想模式之间的偏差
        3. 偏差越小 → 置信度越高

        Args:
            scores: 五维评分结果
            stage:  已判断的市场阶段

        Returns:
            float: 置信度 (0.0 ~ 1.0)
        """
        control = scores.get("control_strength_score", 50.0)
        reserve = scores.get("capital_reserve_score", 50.0)
        follow = scores.get("follow_score", 50.0)
        distribution = scores.get("distribution_risk_score", 50.0)
        fake_move = scores.get("fake_move_risk_score", 50.0)

        # 定义各阶段的"理想评分模式"（每个维度的理想值）
        ideal_patterns: Dict[str, Dict[str, float]] = {
            "accumulation":     {"control": 75, "reserve": 70, "follow": 25, "distribution": 20, "fake_move": 40},
            "markup":           {"control": 70, "reserve": 75, "follow": 55, "distribution": 20, "fake_move": 25},
            "distribution":     {"control": 50, "reserve": 35, "follow": 75, "distribution": 80, "fake_move": 55},
            "markdown":         {"control": 25, "reserve": 25, "follow": 40, "distribution": 65, "fake_move": 40},
            "re_accumulation":  {"control": 60, "reserve": 60, "follow": 45, "distribution": 30, "fake_move": 35},
            "re_distribution":  {"control": 40, "reserve": 40, "follow": 55, "distribution": 60, "fake_move": 60},
            "spring":           {"control": 70, "reserve": 65, "follow": 35, "distribution": 25, "fake_move": 80},
            "upthrust":         {"control": 50, "reserve": 40, "follow": 70, "distribution": 70, "fake_move": 80},
            "uncertain":        {"control": 50, "reserve": 50, "follow": 50, "distribution": 50, "fake_move": 50},
        }

        ideal = ideal_patterns.get(stage, ideal_patterns["uncertain"])

        # 计算实际评分与理想模式的欧氏距离
        # 距离越小 → 匹配度越高 → 置信度越高
        squared_diff_sum = (
            (control - ideal["control"]) ** 2
            + (reserve - ideal["reserve"]) ** 2
            + (follow - ideal["follow"]) ** 2
            + (distribution - ideal["distribution"]) ** 2
            + (fake_move - ideal["fake_move"]) ** 2
        )

        # 最大可能距离：5个维度，每个最大偏差100，总距离 = sqrt(5 * 100^2) ≈ 223.6
        max_possible_distance = (5 * (100.0 ** 2)) ** 0.5
        actual_distance = squared_diff_sum ** 0.5

        # 将距离映射到置信度：距离0 → 置信度1.0，距离最大 → 置信度0.0
        confidence = max(0.0, min(1.0, 1.0 - (actual_distance / max_possible_distance)))

        return round(confidence, 3)

    def _generate_hypothesis_description(
        self,
        stage: str,
        scores: Dict[str, float],
    ) -> str:
        """
        生成该阶段下的主力行为假设文字描述。

        根据市场阶段和具体评分值，生成一段自然语言的行为推断描述。

        Args:
            stage:  市场阶段标识
            scores: 五维评分

        Returns:
            str: 行为假设的中文描述
        """
        control = scores.get("control_strength_score", 50.0)
        reserve = scores.get("capital_reserve_score", 50.0)

        stage_info = MARKET_STAGES.get(stage, MARKET_STAGES["uncertain"])

        # 根据不同阶段生成不同的行为描述
        descriptions: Dict[str, str] = {
            "accumulation": (
                f"当前推断为【{stage_info['name']}】。"
                f"主力控盘强度为 {control:.0f}/100，资金余力为 {reserve:.0f}/100。"
                f"市场表现为缩量横盘整理，散户关注度低。"
                f"主力可能正在低位区间持续吸纳筹码，"
                f"利用市场冷清和散户离场的时机完成建仓计划。"
                f"预计横盘阶段结束后将进入拉升阶段。"
            ),
            "markup": (
                f"当前推断为【{stage_info['name']}】。"
                f"主力控盘强度为 {control:.0f}/100，资金余力为 {reserve:.0f}/100。"
                f"价格呈现趋势性上涨，量价配合良好。"
                f"主力正在积极推升价格，吸引散户跟进以增加市场流动性。"
                f"只要资金余力保持充裕且未出现派发信号，上涨趋势大概率延续。"
            ),
            "distribution": (
                f"当前推断为【{stage_info['name']}】。"
                f"出现量价背离和卖压增大等典型派发信号。"
                f"主力可能正在高位将筹码转移给散户，"
                f"利用利好消息和散户的贪婪情绪完成出货。"
                f"高位放量震荡和频繁插针是典型特征。"
            ),
            "markdown": (
                f"当前推断为【{stage_info['name']}】。"
                f"主力控盘迹象消退，资金余力耗尽。"
                f"价格失去支撑开始趋势性下跌，伴随恐慌性抛售。"
                f"在没有出现明确的止跌信号之前，下跌趋势可能持续。"
            ),
            "spring": (
                f"当前推断为【{stage_info['name']}】。"
                f"价格刚刚假跌破关键支撑位后迅速拉回。"
                f"结合高控盘强度和低派发风险，这大概率是主力的"
                f"最后一次洗盘——借假跌破触发散户止损单后吸纳低价筹码。"
                f"如果价格能站稳支撑位上方，将是优质的入场机会。"
            ),
            "upthrust": (
                f"当前推断为【{stage_info['name']}】。"
                f"价格刚刚假突破关键阻力位后迅速回落。"
                f"结合高派发风险和高跟风度，这很可能是主力的诱多出货——"
                f"借突破吸引追涨散户入场后开始抛售筹码。"
                f"如果价格未能重新站上阻力位，应高度警惕后续下跌。"
            ),
            "re_accumulation": (
                f"当前推断为【{stage_info['name']}】。"
                f"在上涨趋势中出现了中继整理，价格横盘但控盘迹象仍在。"
                f"主力可能在更高价位继续建仓，为下一波拉升蓄力。"
                f"只要不出现派发信号，整理结束后上涨趋势大概率恢复。"
            ),
            "re_distribution": (
                f"当前推断为【{stage_info['name']}】。"
                f"在下跌趋势中出现反弹，但伴随派发信号和假动作风险。"
                f"这可能是主力在较高位置继续出货的中继行为。"
                f"反弹结束后，价格可能重新进入下跌通道。"
            ),
            "uncertain": (
                f"当前阶段判断为【{stage_info['name']}】。"
                f"五维评分之间存在矛盾信号，无法形成一致性的阶段判断。"
                f"建议保持观望，等待更明确的市场信号出现后再做判断。"
            ),
        }

        return descriptions.get(stage, descriptions["uncertain"])

    def _suggest_action_bias(
        self,
        stage: str,
        scores: Dict[str, float],
    ) -> str:
        """
        根据阶段判断给出行动偏向建议。

        这不是具体的交易信号，而是方向性的倾向指引：
        - bullish:  偏多，可寻找做多机会
        - bearish:  偏空，可寻找做空机会或减仓
        - neutral:  中性，观望为主
        - cautious: 谨慎，控制仓位

        Args:
            stage:  市场阶段
            scores: 五维评分

        Returns:
            str: 行动偏向标识
        """
        stage_to_bias: Dict[str, str] = {
            "accumulation": "bullish",         # 吸筹 → 偏多（等待入场时机）
            "markup": "bullish",               # 拉升 → 偏多（顺势做多）
            "distribution": "bearish",         # 派发 → 偏空（准备离场）
            "markdown": "bearish",             # 下跌 → 偏空（顺势做空或空仓）
            "re_accumulation": "bullish",      # 再吸筹 → 偏多（回调买入）
            "re_distribution": "bearish",      # 再派发 → 偏空（反弹做空）
            "spring": "bullish",               # 弹簧 → 偏多（假跌破后做多）
            "upthrust": "bearish",             # 上冲回落 → 偏空（假突破后做空）
            "uncertain": "neutral",            # 不确定 → 中性观望
        }

        bias = stage_to_bias.get(stage, "neutral")

        # 额外检查：即使阶段偏多，如果派发风险过高也要降级为谨慎
        distribution = scores.get("distribution_risk_score", 50.0)
        if bias == "bullish" and distribution >= 65:
            bias = "cautious"

        # 额外检查：即使阶段偏空，如果控盘强度极高也要标记谨慎（主力可能有后手）
        control = scores.get("control_strength_score", 50.0)
        if bias == "bearish" and control >= 70:
            bias = "cautious"

        return bias

    def generate_hypothesis(
        self,
        scores: Dict[str, float],
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        生成完整的行为假设报告。

        这是假设引擎的主入口方法。基于评分引擎的输出，
        生成一份结构化的行为假设 JSON，供交易建议引擎和前端展示使用。

        Args:
            scores:     评分引擎输出的五维评分 Dict
            extra_info: 额外信息（如当前价格、交易对等），用于丰富报告内容

        Returns:
            Dict[str, Any]: 完整的行为假设报告，结构如下：
            {
                "timestamp":   ISO格式时间戳,
                "market_stage": {
                    "stage_key":   阶段标识,
                    "stage_name":  阶段中文名,
                    "description": 阶段描述,
                    "confidence":  置信度 0.0~1.0,
                },
                "hypothesis":   主力行为假设描述文本,
                "action_bias":  行动偏向 (bullish/bearish/neutral/cautious),
                "evidence":     支撑证据列表,
                "risks":        潜在风险列表,
                "scores":       原始五维评分,
                "extra_info":   额外信息（透传）,
            }
        """
        extra_info = extra_info or {}

        logger.info("========== 开始行为假设推断 ==========")

        # 第一步：判断市场阶段
        stage = _determine_market_stage(scores)
        stage_info = MARKET_STAGES.get(stage, MARKET_STAGES["uncertain"])

        # 第二步：计算置信度
        confidence = self._calculate_confidence(scores, stage)

        # 第三步：生成行为假设描述
        hypothesis_text = self._generate_hypothesis_description(stage, scores)

        # 第四步：构建证据列表
        evidence = _build_evidence_list(scores, stage)

        # 第五步：生成风险提示
        risks = _build_risk_list(scores, stage)

        # 第六步：确定行动偏向
        action_bias = self._suggest_action_bias(stage, scores)

        # 组装完整的假设报告
        hypothesis_report: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_stage": {
                "stage_key": stage,
                "stage_name": stage_info["name"],
                "description": stage_info["description"],
                "confidence": confidence,
            },
            "hypothesis": hypothesis_text,
            "action_bias": action_bias,
            "evidence": evidence,
            "risks": risks,
            "scores": scores,
            "extra_info": extra_info,
        }

        logger.info(
            f"行为假设推断完成: 阶段={stage_info['name']}, "
            f"置信度={confidence:.1%}, 偏向={action_bias}"
        )

        return hypothesis_report

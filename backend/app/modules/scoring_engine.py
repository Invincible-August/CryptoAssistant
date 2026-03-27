"""
评分引擎模块。

职责：
1. 接收特征管线输出的全部因子结果
2. 按照预定义的维度和权重体系，将因子结果转化为多维度综合评分
3. 输出五个核心维度的评分，供假设引擎和建议引擎使用

五大评分维度（对应庄家行为分析框架）：
- 控盘强度 (control_strength_score):   主力对盘面的控制程度
- 资金余力 (capital_reserve_score):     主力剩余可用资金的充裕程度
- 跟风可利用度 (follow_score):          散户跟风情绪的可利用程度
- 派发风险 (distribution_risk_score):   主力出货的风险信号强度
- 假动作风险 (fake_move_risk_score):    价格假突破/假跌破的概率

评分范围：所有评分归一化到 0-100 区间，0 表示极弱/极低，100 表示极强/极高。
"""
from typing import Any, Dict, List, Optional

from loguru import logger


# ========== 评分维度的因子权重配置 ==========
# 每个维度由哪些因子组成，以及每个因子在该维度中的权重

# 控盘强度维度：由成交量分布、价格走势平稳度、大单占比等因子决定
CONTROL_STRENGTH_WEIGHTS: Dict[str, float] = {
    "volume_concentration": 0.25,      # 成交量集中度 —— 高集中度说明主力在定向操作
    "price_efficiency": 0.20,          # 价格效率 —— 价格变动相对成交量的效率
    "large_order_ratio": 0.25,         # 大单占比 —— 大单比例越高，控盘越明显
    "spread_stability": 0.15,          # 盘口价差稳定性 —— 稳定说明有人在维护盘口
    "wick_ratio": 0.15,               # 上下影线比例 —— 影线过长说明控盘能力不足
}

# 资金余力维度：反映主力还能投入多少资金继续操作
CAPITAL_RESERVE_WEIGHTS: Dict[str, float] = {
    "open_interest_trend": 0.30,       # 持仓量趋势 —— 持仓持续增加说明资金在流入
    "funding_rate_pressure": 0.20,     # 资金费率压力 —— 费率过高意味着维持成本大
    "volume_sustainability": 0.25,     # 成交量可持续性 —— 量能是否在衰减
    "margin_utilization": 0.25,        # 保证金使用率 —— 使用率过高说明杠杆到极限
}

# 跟风可利用度维度：散户情绪和行为是否对主力有利
FOLLOW_SCORE_WEIGHTS: Dict[str, float] = {
    "retail_sentiment": 0.30,          # 散户情绪指数 —— 情绪过于一致时容易被利用
    "fomo_intensity": 0.25,            # FOMO（怕踏空）强度 —— 追涨杀跌的程度
    "social_momentum": 0.20,           # 社交媒体动量 —— 舆论热度对散户行为的放大效应
    "long_short_ratio": 0.25,          # 多空比例 —— 单边仓位过重时容易被收割
}

# 派发风险维度：主力是否在高位出货的信号
DISTRIBUTION_RISK_WEIGHTS: Dict[str, float] = {
    "volume_price_divergence": 0.30,   # 量价背离 —— 价格新高但量能萎缩，典型派发信号
    "selling_pressure": 0.25,          # 卖压指标 —— 卖盘挂单深度和成交速度
    "whale_transfer": 0.20,            # 大户转账 —— 链上大额转入交易所，可能准备出货
    "momentum_exhaustion": 0.25,       # 动量耗尽 —— RSI/MACD 等动量指标出现顶背离
}

# 假动作风险维度：价格可能在做虚假突破/跌破的概率
FAKE_MOVE_RISK_WEIGHTS: Dict[str, float] = {
    "breakout_volume_confirm": 0.30,   # 突破量能确认 —— 突破时成交量是否放大到足够倍数
    "support_resistance_test": 0.25,   # 支撑/阻力测试次数 —— 反复试探同一位置
    "stop_hunt_pattern": 0.25,         # 止损猎杀模式 —— 快速刺穿关键位后迅速回收
    "order_book_spoofing": 0.20,       # 挂单欺诈 —— 大额挂单出现后迅速撤单
}


def _clamp_score(raw_score: float) -> float:
    """
    将原始评分钳位到 [0, 100] 区间。

    避免极端因子值导致评分溢出合法范围。

    Args:
        raw_score: 原始计算的评分值

    Returns:
        float: 钳位后的评分值
    """
    return max(0.0, min(100.0, raw_score))


def _extract_factor_score(
    factor_results: Dict[str, Dict],
    factor_key: str,
    score_field: str = "score",
    default_value: float = 50.0,
) -> float:
    """
    从因子结果集中安全地提取某个因子的评分值。

    当因子未计算或结果中缺少评分字段时，返回默认值（中性分50）。
    这样可以保证即使部分因子缺失，评分引擎也能输出合理的结果。

    Args:
        factor_results: 特征管线输出的全部因子结果 {factor_key: {field: value}}
        factor_key:     要提取的因子 key
        score_field:    评分字段名，默认为 "score"
        default_value:  因子缺失时的默认评分（50 = 中性）

    Returns:
        float: 提取到的因子评分值
    """
    factor_data = factor_results.get(factor_key)
    if factor_data is None:
        # 因子未计算 —— 使用中性默认值，避免影响综合评分
        logger.debug(f"因子 {factor_key} 无数据，使用默认值 {default_value}")
        return default_value

    score_value = factor_data.get(score_field, default_value)

    # 类型保护：确保返回值为数值类型
    if not isinstance(score_value, (int, float)):
        logger.warning(
            f"因子 {factor_key} 的 {score_field} 字段类型异常: "
            f"{type(score_value)}，使用默认值"
        )
        return default_value

    return float(score_value)


def _compute_weighted_score(
    factor_results: Dict[str, Dict],
    weight_config: Dict[str, float],
) -> float:
    """
    根据权重配置计算某个维度的加权综合评分。

    计算公式：
        score = Σ (factor_score_i × weight_i) / Σ (weight_i)

    使用归一化权重（除以权重总和），这样即使部分因子的权重配置
    总和不精确为1.0，也能保证输出在合理范围内。

    Args:
        factor_results: 全部因子结果集
        weight_config:  该维度的因子权重配置 {factor_key: weight}

    Returns:
        float: 加权综合评分（0-100 区间）
    """
    total_weight = 0.0
    weighted_score_sum = 0.0

    for factor_key, weight in weight_config.items():
        # 提取因子评分
        factor_score = _extract_factor_score(factor_results, factor_key)

        # 累加加权分
        weighted_score_sum += factor_score * weight
        total_weight += weight

    # 防止除零（所有权重为0的极端情况）
    if total_weight <= 0:
        logger.warning("权重总和为0，返回中性评分50")
        return 50.0

    # 加权平均 → 归一化
    raw_score = weighted_score_sum / total_weight
    return _clamp_score(raw_score)


class ScoringEngine:
    """
    多维度评分引擎。

    接收特征管线输出的因子结果，通过预定义的权重矩阵，
    计算出五个核心维度的综合评分：

    1. 控盘强度 (control_strength_score)
       衡量主力对当前盘面的掌控力度。高分意味着主力在积极操盘，
       价格走势更可能按主力意图运行。

    2. 资金余力 (capital_reserve_score)
       衡量主力还有多少"弹药"可以继续操作。高分意味着行情
       还有延续空间，低分意味着主力可能力竭。

    3. 跟风可利用度 (follow_score)
       衡量散户情绪是否处于容易被主力利用的状态。高分意味着
       散户情绪极端，容易出现反转行情。

    4. 派发风险 (distribution_risk_score)
       衡量主力在高位出货的概率。高分意味着出现了明显的派发信号，
       行情可能即将反转下跌。

    5. 假动作风险 (fake_move_risk_score)
       衡量当前价格突破/跌破的真实性。高分意味着突破缺乏量能确认，
       可能是诱多/诱空的假动作。

    Attributes:
        _custom_weights: 自定义权重覆盖，允许运行时调整权重
    """

    def __init__(self) -> None:
        """初始化评分引擎，使用默认权重配置。"""
        # 允许运行时覆盖默认权重，key 为维度名称，value 为该维度的权重配置
        self._custom_weights: Dict[str, Dict[str, float]] = {}

    def set_custom_weights(
        self,
        dimension: str,
        weights: Dict[str, float],
    ) -> None:
        """
        为指定维度设置自定义因子权重。

        可以在不修改代码的情况下调整各维度的因子权重组合，
        适用于不同市场环境下的权重优化。

        Args:
            dimension: 维度名称，如 "control_strength"、"distribution_risk"
            weights:   因子权重字典 {factor_key: weight}
        """
        self._custom_weights[dimension] = weights
        logger.info(f"已设置 {dimension} 维度的自定义权重: {weights}")

    def _get_weights(
        self,
        dimension: str,
        default_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """
        获取指定维度的权重配置（优先使用自定义权重）。

        Args:
            dimension:       维度名称
            default_weights: 默认权重配置

        Returns:
            Dict[str, float]: 最终使用的权重配置
        """
        return self._custom_weights.get(dimension, default_weights)

    def compute_control_strength(
        self,
        factor_results: Dict[str, Dict],
    ) -> float:
        """
        计算控盘强度评分。

        控盘强度反映主力对市场的掌控程度。当以下条件同时成立时，
        控盘强度评分会较高：
        - 成交量高度集中在少数时段（说明定向操作）
        - 价格变动效率高（少量成交就能推动价格）
        - 大单成交占比大
        - 盘口价差稳定（有人在维护）
        - 影线比例小（走势干脆利落）

        Args:
            factor_results: 全部因子结果

        Returns:
            float: 控盘强度评分 (0-100)
        """
        weights = self._get_weights("control_strength", CONTROL_STRENGTH_WEIGHTS)
        score = _compute_weighted_score(factor_results, weights)
        logger.debug(f"控盘强度评分: {score:.2f}")
        return score

    def compute_capital_reserve(
        self,
        factor_results: Dict[str, Dict],
    ) -> float:
        """
        计算资金余力评分。

        资金余力衡量主力是否还有足够的资金继续操作。
        当以下条件成立时评分较高：
        - 持仓量（OI）持续增长，说明新资金在流入
        - 资金费率处于合理水平，维持成本不高
        - 成交量保持稳定或增长，量能未衰减
        - 保证金使用率不高，杠杆还有空间

        反之，如果持仓下降、费率极端、量能萎缩、杠杆到顶，
        则说明主力已经"弹尽粮绝"，行情可能即将转向。

        Args:
            factor_results: 全部因子结果

        Returns:
            float: 资金余力评分 (0-100)
        """
        weights = self._get_weights("capital_reserve", CAPITAL_RESERVE_WEIGHTS)
        score = _compute_weighted_score(factor_results, weights)
        logger.debug(f"资金余力评分: {score:.2f}")
        return score

    def compute_follow_score(
        self,
        factor_results: Dict[str, Dict],
    ) -> float:
        """
        计算跟风可利用度评分。

        跟风可利用度衡量散户情绪是否处于容易被主力利用的状态。

        当散户情绪极度乐观（贪婪）或极度恐慌时，跟风可利用度最高——
        主力可以利用散户的一致性行为来完成自己的建仓或出货。

        具体表现：
        - 散户情绪指数处于极端值（极度贪婪或极度恐慌）
        - FOMO 强度高（追涨杀跌行为明显）
        - 社交媒体上某个方向的讨论热度过高
        - 多空比例严重失衡

        Args:
            factor_results: 全部因子结果

        Returns:
            float: 跟风可利用度评分 (0-100)
        """
        weights = self._get_weights("follow_score", FOLLOW_SCORE_WEIGHTS)
        score = _compute_weighted_score(factor_results, weights)
        logger.debug(f"跟风可利用度评分: {score:.2f}")
        return score

    def compute_distribution_risk(
        self,
        factor_results: Dict[str, Dict],
    ) -> float:
        """
        计算派发风险评分。

        派发（Distribution）是主力在高位将筹码转移给散户的过程。
        以下信号越强，派发风险越高：

        - 量价背离：价格创新高但成交量反而萎缩，
          说明高位缺乏买盘支撑，主力可能在借拉升出货
        - 卖压增大：卖方挂单量增加，大额卖单频繁成交
        - 大户链上转账：大额代币从冷钱包转入交易所，可能准备抛售
        - 动量耗尽：RSI 进入超买区后回落，MACD 出现死叉，
          表明上涨动能正在衰竭

        Args:
            factor_results: 全部因子结果

        Returns:
            float: 派发风险评分 (0-100)
        """
        weights = self._get_weights("distribution_risk", DISTRIBUTION_RISK_WEIGHTS)
        score = _compute_weighted_score(factor_results, weights)
        logger.debug(f"派发风险评分: {score:.2f}")
        return score

    def compute_fake_move_risk(
        self,
        factor_results: Dict[str, Dict],
    ) -> float:
        """
        计算假动作风险评分。

        假动作（Fake Move）是主力制造虚假的突破或跌破，
        诱使散户做出错误方向的交易决策后反向收割。

        识别依据：
        - 突破时成交量不足：真突破伴随放量，假突破量能萎靡
        - 反复测试支撑/阻力位：多次测试但无法真正突破
        - 止损猎杀模式：快速刺穿关键价位触发大量止损单后迅速回收
        - 挂单欺诈：大额挂单短暂出现后迅速撤单，制造虚假的支撑/阻力

        高分意味着当前的突破/跌破可能是假动作，不宜追单。

        Args:
            factor_results: 全部因子结果

        Returns:
            float: 假动作风险评分 (0-100)
        """
        weights = self._get_weights("fake_move_risk", FAKE_MOVE_RISK_WEIGHTS)
        score = _compute_weighted_score(factor_results, weights)
        logger.debug(f"假动作风险评分: {score:.2f}")
        return score

    def compute_all_scores(
        self,
        factor_results: Dict[str, Dict],
    ) -> Dict[str, float]:
        """
        一次性计算所有维度的评分。

        这是评分引擎的主入口方法，依次计算五个核心维度的评分并汇总返回。

        Args:
            factor_results: 特征管线输出的全部因子结果
                格式: {factor_key: {"score": float, ...other_fields}}

        Returns:
            Dict[str, float]: 五维评分结果，结构如下：
                {
                    "control_strength_score":   float,  # 控盘强度 0-100
                    "capital_reserve_score":     float,  # 资金余力 0-100
                    "follow_score":              float,  # 跟风可利用度 0-100
                    "distribution_risk_score":   float,  # 派发风险 0-100
                    "fake_move_risk_score":       float,  # 假动作风险 0-100
                }
        """
        logger.info("========== 开始多维度评分计算 ==========")

        all_scores: Dict[str, float] = {
            "control_strength_score": self.compute_control_strength(factor_results),
            "capital_reserve_score": self.compute_capital_reserve(factor_results),
            "follow_score": self.compute_follow_score(factor_results),
            "distribution_risk_score": self.compute_distribution_risk(factor_results),
            "fake_move_risk_score": self.compute_fake_move_risk(factor_results),
        }

        logger.info(
            f"多维度评分计算完成: "
            f"控盘={all_scores['control_strength_score']:.1f}, "
            f"余力={all_scores['capital_reserve_score']:.1f}, "
            f"跟风={all_scores['follow_score']:.1f}, "
            f"派发={all_scores['distribution_risk_score']:.1f}, "
            f"假动={all_scores['fake_move_risk_score']:.1f}"
        )

        return all_scores

    def compute_composite_score(
        self,
        all_scores: Dict[str, float],
    ) -> float:
        """
        计算综合评分（单一数值汇总）。

        将五维评分通过加权平均合成为一个综合评分。
        综合评分的含义：
        - 高分 (>70): 多头环境强，主力控盘、资金充裕、散户可被利用
        - 中分 (40-70): 市场方向不明，观望为主
        - 低分 (<40): 风险信号密集，主力可能出货或制造假动作

        权重设计：
        - 控盘强度和资金余力是正面因子（高分 = 好）
        - 派发风险和假动作风险是负面因子（高分 = 差，需要反转）
        - 跟风可利用度是中性因子（需要结合方向判断）

        Args:
            all_scores: compute_all_scores 的输出

        Returns:
            float: 综合评分 (0-100)
        """
        # 正面因子：控盘强度和资金余力越高越好
        positive_component = (
            all_scores.get("control_strength_score", 50.0) * 0.25
            + all_scores.get("capital_reserve_score", 50.0) * 0.25
        )

        # 负面因子：派发风险和假动作风险越高越差，需要反转（用100减去）
        negative_component = (
            (100.0 - all_scores.get("distribution_risk_score", 50.0)) * 0.20
            + (100.0 - all_scores.get("fake_move_risk_score", 50.0)) * 0.15
        )

        # 中性因子：跟风可利用度，高分说明市场情绪极端，可利用但需谨慎
        neutral_component = all_scores.get("follow_score", 50.0) * 0.15

        composite = _clamp_score(positive_component + negative_component + neutral_component)
        logger.info(f"综合评分: {composite:.2f}")
        return composite

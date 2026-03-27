"""
AI提示词构建模块。
根据市场数据、指标结果、因子评分等信息，
构建结构化的Prompt发送给大模型，引导AI输出JSON格式的分析结果。
"""
from typing import Any, Dict, List, Optional


# ==================== 系统级Prompt模板 ====================

# 市场综合分析的系统提示词：定义AI的角色、输出格式和分析框架
_ANALYSIS_SYSTEM_PROMPT = """你是一位专业的加密货币量化分析师。
你需要根据提供的市场数据、技术指标和多因子评分，对指定交易对进行综合分析。

请严格按照以下JSON格式输出分析结果（不要包含markdown代码块标记）：
{
    "direction": "long 或 short 或 neutral",
    "confidence": 0.0到1.0之间的置信度,
    "win_rate": 0.0到1.0之间的预估胜率,
    "entry_zone": {"low": 入场下限价格, "high": 入场上限价格},
    "stop_loss": 止损价位,
    "take_profits": [
        {"price": 止盈价位1, "ratio": 仓位比例1},
        {"price": 止盈价位2, "ratio": 仓位比例2}
    ],
    "scores": {
        "trend": 趋势评分0-100,
        "momentum": 动量评分0-100,
        "volatility": 波动率评分0-100,
        "volume": 成交量评分0-100,
        "microstructure": 微观结构评分0-100
    },
    "hypotheses": ["市场假设1", "市场假设2"],
    "evidence": ["支撑论据1", "支撑论据2"],
    "risks": ["风险因素1", "风险因素2"],
    "summary": "一段完整的中文分析总结"
}

分析要求：
1. 综合考虑所有指标和因子数据，不要偏重单一指标
2. 置信度必须基于数据支撑，不确定时应该给出较低的置信度
3. 止损位设置必须合理，考虑波动率和支撑/阻力位
4. 多级止盈应考虑不同的目标位和仓位管理
5. 风险因素必须包含当前市场环境的主要不确定性
6. 所有文字内容必须使用中文"""

# 指标建议的系统提示词：引导AI根据当前指标配置建议新指标
_INDICATOR_SUGGESTION_SYSTEM_PROMPT = """你是一位量化交易指标设计专家。
根据当前交易对使用的指标列表和市场环境，建议一个新的技术指标。

请严格按照以下JSON格式输出（不要包含markdown代码块标记）：
{
    "indicator_key": "指标唯一标识（英文蛇形命名，如 adaptive_rsi）",
    "name": "指标中文名称",
    "description": "指标描述，说明计算逻辑和适用场景",
    "category": "trend 或 momentum 或 volume 或 volatility 或 custom",
    "params_schema": {
        "参数名": {
            "type": "int/float/str/bool",
            "default": 默认值,
            "required": true或false,
            "description": "参数描述"
        }
    },
    "output_schema": {
        "字段名": {
            "type": "float/int/str",
            "description": "输出字段描述"
        }
    },
    "calculation_logic": "详细的计算逻辑描述（中文）",
    "reason": "建议理由，为什么在当前市场环境下需要这个指标"
}

要求：
1. 建议的指标不能与已有指标功能重复
2. 指标设计要有实际的量化交易价值
3. 参数设计要合理，带有明确的默认值
4. 计算逻辑要具体可实现，不能过于抽象"""

# 因子建议的系统提示词：引导AI建议新的多因子评分因子
_FACTOR_SUGGESTION_SYSTEM_PROMPT = """你是一位量化交易多因子模型设计专家。
根据当前交易对使用的因子列表和市场环境，建议一个新的分析因子。

请严格按照以下JSON格式输出（不要包含markdown代码块标记）：
{
    "factor_key": "因子唯一标识（英文蛇形命名，如 whale_accumulation）",
    "name": "因子中文名称",
    "description": "因子描述，说明计算逻辑和适用场景",
    "category": "momentum 或 volatility 或 flow 或 microstructure 或 positioning 或 custom",
    "input_type": ["依赖的数据源列表，如 kline, orderbook, trades"],
    "params_schema": {
        "参数名": {
            "type": "int/float/str/bool",
            "default": 默认值,
            "required": true或false,
            "description": "参数描述"
        }
    },
    "output_schema": {
        "字段名": {
            "type": "float/int/str",
            "description": "输出字段描述"
        }
    },
    "score_weight": 建议的评分权重（0.1到3.0之间的浮点数）,
    "calculation_logic": "详细的计算逻辑描述（中文）",
    "reason": "建议理由，解释该因子如何补充现有因子体系"
}

要求：
1. 因子不能与已有因子功能重复
2. 因子需要有明确的数据源依赖声明
3. 因子评分权重要合理，不能过大导致单因子主导
4. 因子设计要考虑与其他因子的互补性"""


def build_analysis_prompt(
    symbol: str,
    market_summary: Dict[str, Any],
    indicators: List[Dict[str, Any]],
    factors: List[Dict[str, Any]],
    behavior_profile: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    构建市场综合分析的Prompt消息列表。

    将交易对的行情概览、技术指标结果、多因子评分和行为画像
    组装成结构化的用户消息，配合系统提示词发送给AI模型。

    Args:
        symbol: 交易对名称，如 "BTCUSDT"
        market_summary: 行情概览数据，包含价格、涨跌幅、成交量等
        indicators: 技术指标结果列表，每项包含指标名和计算值
        factors: 多因子评分列表，每项包含因子名和评分
        behavior_profile: 主力行为画像数据（可选），包含主力资金流向等

    Returns:
        List[Dict[str, str]]: OpenAI消息格式的列表，包含system和user两条消息
    """
    # ---- 拼装用户消息：逐块组装市场数据 ----
    user_content_parts: List[str] = [
        f"## 分析目标\n交易对: {symbol}\n",
    ]

    # 行情概览部分
    if market_summary:
        user_content_parts.append("## 行情概览")
        for key, value in market_summary.items():
            user_content_parts.append(f"- {key}: {value}")
        user_content_parts.append("")

    # 技术指标数据部分
    if indicators:
        user_content_parts.append("## 技术指标数据")
        for indicator_data in indicators:
            indicator_name = indicator_data.get("name", indicator_data.get("indicator_key", "未知指标"))
            user_content_parts.append(f"\n### {indicator_name}")
            # 最新值优先展示
            latest = indicator_data.get("latest")
            if latest:
                user_content_parts.append(f"最新值: {latest}")
            # 近期序列作为补充
            series = indicator_data.get("series")
            if series:
                user_content_parts.append(f"近期数据（最近{len(series)}条）: {series}")
        user_content_parts.append("")

    # 多因子评分部分
    if factors:
        user_content_parts.append("## 多因子评分")
        for factor_data in factors:
            factor_name = factor_data.get("name", factor_data.get("factor_key", "未知因子"))
            score = factor_data.get("score", "N/A")
            direction = factor_data.get("direction", "N/A")
            user_content_parts.append(f"- {factor_name}: 评分={score}, 方向={direction}")
        user_content_parts.append("")

    # 主力行为画像部分（可选）
    if behavior_profile:
        user_content_parts.append("## 主力行为画像")
        for key, value in behavior_profile.items():
            user_content_parts.append(f"- {key}: {value}")
        user_content_parts.append("")

    user_content = "\n".join(user_content_parts)

    return [
        {"role": "system", "content": _ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def build_indicator_suggestion_prompt(
    symbol: str,
    current_indicators: List[Dict[str, Any]],
    market_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    构建指标建议的Prompt消息列表。

    将当前已有的指标列表和市场环境信息提供给AI，
    让AI建议一个新的有价值的技术指标。

    Args:
        symbol: 交易对名称
        current_indicators: 当前已配置的指标列表，每项包含key、name、category等
        market_context: 当前市场环境信息（可选），如波动率状态、趋势阶段等

    Returns:
        List[Dict[str, str]]: OpenAI消息格式的列表
    """
    # 整理当前已有指标的摘要信息
    indicator_summary_lines: List[str] = []
    for ind in current_indicators:
        indicator_key = ind.get("indicator_key", "unknown")
        name = ind.get("name", "未知")
        category = ind.get("category", "custom")
        indicator_summary_lines.append(
            f"  - {indicator_key} ({name}), 分类: {category}"
        )
    indicator_list_text = "\n".join(indicator_summary_lines) if indicator_summary_lines else "  暂无已配置指标"

    # 组装用户消息
    user_parts: List[str] = [
        f"## 交易对: {symbol}\n",
        f"## 当前已有指标\n{indicator_list_text}\n",
    ]

    # 附加市场环境信息
    if market_context:
        user_parts.append("## 当前市场环境")
        for key, value in market_context.items():
            user_parts.append(f"- {key}: {value}")
        user_parts.append("")

    user_parts.append("请基于以上信息，建议一个对当前交易对有价值的新技术指标。")

    return [
        {"role": "system", "content": _INDICATOR_SUGGESTION_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def build_factor_suggestion_prompt(
    symbol: str,
    current_factors: List[Dict[str, Any]],
    market_context: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    构建因子建议的Prompt消息列表。

    将当前已有的因子列表和市场环境信息提供给AI，
    让AI建议一个新的多因子评分因子。

    Args:
        symbol: 交易对名称
        current_factors: 当前已配置的因子列表，每项包含key、name、category等
        market_context: 当前市场环境信息（可选）

    Returns:
        List[Dict[str, str]]: OpenAI消息格式的列表
    """
    # 整理当前已有因子的摘要信息
    factor_summary_lines: List[str] = []
    for fac in current_factors:
        factor_key = fac.get("factor_key", "unknown")
        name = fac.get("name", "未知")
        category = fac.get("category", "custom")
        weight = fac.get("score_weight", 1.0)
        factor_summary_lines.append(
            f"  - {factor_key} ({name}), 分类: {category}, 权重: {weight}"
        )
    factor_list_text = "\n".join(factor_summary_lines) if factor_summary_lines else "  暂无已配置因子"

    # 组装用户消息
    user_parts: List[str] = [
        f"## 交易对: {symbol}\n",
        f"## 当前已有因子\n{factor_list_text}\n",
    ]

    # 附加市场环境信息
    if market_context:
        user_parts.append("## 当前市场环境")
        for key, value in market_context.items():
            user_parts.append(f"- {key}: {value}")
        user_parts.append("")

    user_parts.append("请基于以上信息，建议一个能补充现有因子体系的新分析因子。")

    return [
        {"role": "system", "content": _FACTOR_SUGGESTION_SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]

"""
AI输出验证模块。
对AI模型返回的结构化数据进行业务规则校验，
确保关键字段存在且数值在合理范围内，防止异常数据流入下游。
"""
from typing import Any, Dict, List

from loguru import logger


# ==================== 合法的枚举值集合 ====================
# 交易方向允许值，与 SignalDirection 枚举保持一致
_VALID_DIRECTIONS = {"long", "short", "neutral"}

# 指标分类允许值，与系统指标分类体系保持一致
_VALID_INDICATOR_CATEGORIES = {"trend", "momentum", "volume", "volatility", "custom"}

# 因子分类允许值，与系统因子分类体系保持一致
_VALID_FACTOR_CATEGORIES = {
    "momentum", "volatility", "flow", "microstructure", "positioning", "custom",
}

# 因子数据源允许值，与系统支持的数据类型保持一致
_VALID_INPUT_TYPES = {"kline", "orderbook", "open_interest", "funding_rate", "trades"}


def validate_analysis_result(result: Dict[str, Any]) -> bool:
    """
    验证AI市场分析结果的完整性和合理性。

    校验规则：
    1. direction 必须是 long/short/neutral 之一
    2. confidence 必须在 [0.0, 1.0] 区间
    3. win_rate 必须在 [0.0, 1.0] 区间
    4. summary 不能为空字符串
    5. 如果有止盈列表，每项必须包含 price 和 ratio
    6. 解析错误标记 _parse_error 不能为 True

    Args:
        result: parse_analysis_response() 返回的分析结果字典

    Returns:
        bool: 验证通过返回True，任一校验失败返回False
    """
    validation_errors: List[str] = []

    # 检查是否存在解析错误标记（parser模块在解析失败时会设置此标记）
    if result.get("_parse_error"):
        validation_errors.append("分析结果存在解析错误标记")

    # ---- 交易方向校验 ----
    direction = result.get("direction")
    if direction not in _VALID_DIRECTIONS:
        validation_errors.append(
            f"direction值无效: '{direction}'，允许值: {_VALID_DIRECTIONS}"
        )

    # ---- 置信度范围校验 ----
    confidence = result.get("confidence")
    if not _is_valid_ratio(confidence):
        validation_errors.append(
            f"confidence值超出范围: {confidence}，应在[0.0, 1.0]区间"
        )

    # ---- 胜率范围校验 ----
    win_rate = result.get("win_rate")
    if not _is_valid_ratio(win_rate):
        validation_errors.append(
            f"win_rate值超出范围: {win_rate}，应在[0.0, 1.0]区间"
        )

    # ---- 分析摘要非空校验 ----
    summary = result.get("summary")
    if not summary or not isinstance(summary, str) or not summary.strip():
        validation_errors.append("summary不能为空")

    # ---- 止盈列表结构校验（可选字段，存在时需校验） ----
    take_profits = result.get("take_profits", [])
    if take_profits and isinstance(take_profits, list):
        for idx, tp_item in enumerate(take_profits):
            if not isinstance(tp_item, dict):
                validation_errors.append(f"take_profits[{idx}]不是字典类型")
                continue
            if "price" not in tp_item:
                validation_errors.append(f"take_profits[{idx}]缺少price字段")
            if "ratio" not in tp_item:
                validation_errors.append(f"take_profits[{idx}]缺少ratio字段")

    # ---- 入场区间结构校验（可选字段） ----
    entry_zone = result.get("entry_zone")
    if entry_zone is not None:
        if not isinstance(entry_zone, dict):
            validation_errors.append("entry_zone必须是字典类型")
        elif "low" not in entry_zone or "high" not in entry_zone:
            validation_errors.append("entry_zone必须包含low和high字段")

    # ---- 汇总校验结果 ----
    if validation_errors:
        for error_msg in validation_errors:
            logger.warning(f"AI分析结果校验失败: {error_msg}")
        return False

    logger.info("AI分析结果校验通过")
    return True


def validate_indicator_proposal(proposal: Dict[str, Any]) -> bool:
    """
    验证AI指标建议草案的完整性和合理性。

    校验规则：
    1. indicator_key 必须是非空字符串且符合蛇形命名（小写+下划线）
    2. name 必须是非空字符串
    3. category 必须是合法的指标分类
    4. params_schema 必须是字典类型
    5. output_schema 必须是字典类型
    6. calculation_logic 必须是非空字符串（确保AI给出了实现思路）

    Args:
        proposal: parse_indicator_suggestion() 返回的指标建议字典

    Returns:
        bool: 验证通过返回True，任一校验失败返回False
    """
    validation_errors: List[str] = []

    # 检查是否存在解析错误标记
    if proposal.get("_parse_error"):
        validation_errors.append("指标建议存在解析错误标记")

    # ---- 指标标识校验（必须是合法的蛇形命名） ----
    indicator_key = proposal.get("indicator_key", "")
    if not indicator_key or not isinstance(indicator_key, str):
        validation_errors.append("indicator_key不能为空")
    elif not _is_valid_snake_case(indicator_key):
        validation_errors.append(
            f"indicator_key格式无效: '{indicator_key}'，需为小写字母和下划线组成"
        )

    # ---- 名称非空校验 ----
    name = proposal.get("name", "")
    if not name or not isinstance(name, str) or not name.strip():
        validation_errors.append("name不能为空")

    # ---- 分类校验 ----
    category = proposal.get("category", "")
    if category not in _VALID_INDICATOR_CATEGORIES:
        validation_errors.append(
            f"category值无效: '{category}'，允许值: {_VALID_INDICATOR_CATEGORIES}"
        )

    # ---- Schema类型校验 ----
    if not isinstance(proposal.get("params_schema"), dict):
        validation_errors.append("params_schema必须是字典类型")
    if not isinstance(proposal.get("output_schema"), dict):
        validation_errors.append("output_schema必须是字典类型")

    # ---- 计算逻辑非空校验 ----
    calc_logic = proposal.get("calculation_logic", "")
    if not calc_logic or not isinstance(calc_logic, str) or not calc_logic.strip():
        validation_errors.append("calculation_logic不能为空")

    # ---- 汇总校验结果 ----
    if validation_errors:
        for error_msg in validation_errors:
            logger.warning(f"AI指标建议校验失败: {error_msg}")
        return False

    logger.info(f"AI指标建议校验通过: {indicator_key}")
    return True


def validate_factor_proposal(proposal: Dict[str, Any]) -> bool:
    """
    验证AI因子建议草案的完整性和合理性。

    校验规则：
    1. factor_key 必须是非空字符串且符合蛇形命名
    2. name 必须是非空字符串
    3. category 必须是合法的因子分类
    4. input_type 必须是非空列表，且每项都是合法的数据源类型
    5. params_schema 和 output_schema 必须是字典类型
    6. score_weight 必须在 (0.0, 5.0] 区间（防止单因子权重过大）
    7. calculation_logic 必须是非空字符串

    Args:
        proposal: parse_factor_suggestion() 返回的因子建议字典

    Returns:
        bool: 验证通过返回True，任一校验失败返回False
    """
    validation_errors: List[str] = []

    # 检查是否存在解析错误标记
    if proposal.get("_parse_error"):
        validation_errors.append("因子建议存在解析错误标记")

    # ---- 因子标识校验 ----
    factor_key = proposal.get("factor_key", "")
    if not factor_key or not isinstance(factor_key, str):
        validation_errors.append("factor_key不能为空")
    elif not _is_valid_snake_case(factor_key):
        validation_errors.append(
            f"factor_key格式无效: '{factor_key}'，需为小写字母和下划线组成"
        )

    # ---- 名称非空校验 ----
    name = proposal.get("name", "")
    if not name or not isinstance(name, str) or not name.strip():
        validation_errors.append("name不能为空")

    # ---- 分类校验 ----
    category = proposal.get("category", "")
    if category not in _VALID_FACTOR_CATEGORIES:
        validation_errors.append(
            f"category值无效: '{category}'，允许值: {_VALID_FACTOR_CATEGORIES}"
        )

    # ---- 数据源依赖校验 ----
    input_type = proposal.get("input_type", [])
    if not isinstance(input_type, list) or len(input_type) == 0:
        validation_errors.append("input_type必须是非空列表")
    else:
        for item in input_type:
            if item not in _VALID_INPUT_TYPES:
                validation_errors.append(
                    f"input_type中包含无效值: '{item}'，允许值: {_VALID_INPUT_TYPES}"
                )

    # ---- Schema类型校验 ----
    if not isinstance(proposal.get("params_schema"), dict):
        validation_errors.append("params_schema必须是字典类型")
    if not isinstance(proposal.get("output_schema"), dict):
        validation_errors.append("output_schema必须是字典类型")

    # ---- 评分权重范围校验（防止单因子主导整体评分） ----
    score_weight = proposal.get("score_weight")
    try:
        weight_float = float(score_weight)
        if weight_float <= 0.0 or weight_float > 5.0:
            validation_errors.append(
                f"score_weight超出范围: {weight_float}，应在(0.0, 5.0]区间"
            )
    except (ValueError, TypeError):
        validation_errors.append(f"score_weight无法转为浮点数: {score_weight}")

    # ---- 计算逻辑非空校验 ----
    calc_logic = proposal.get("calculation_logic", "")
    if not calc_logic or not isinstance(calc_logic, str) or not calc_logic.strip():
        validation_errors.append("calculation_logic不能为空")

    # ---- 汇总校验结果 ----
    if validation_errors:
        for error_msg in validation_errors:
            logger.warning(f"AI因子建议校验失败: {error_msg}")
        return False

    logger.info(f"AI因子建议校验通过: {factor_key}")
    return True


# ==================== 内部工具函数 ====================


def _is_valid_ratio(value: Any) -> bool:
    """
    校验值是否为合法的比率（0.0到1.0之间的浮点数）。

    Args:
        value: 需要校验的值

    Returns:
        bool: 合法返回True，否则返回False
    """
    if value is None:
        return False
    try:
        float_val = float(value)
        return 0.0 <= float_val <= 1.0
    except (ValueError, TypeError):
        return False


def _is_valid_snake_case(text: str) -> bool:
    """
    校验字符串是否符合蛇形命名规范（仅包含小写字母、数字和下划线）。

    蛇形命名是因子和指标标识符的标准格式，
    如 "adaptive_rsi"、"whale_accumulation" 等。

    Args:
        text: 需要校验的字符串

    Returns:
        bool: 符合蛇形命名返回True，否则返回False
    """
    import re
    # 蛇形命名：以小写字母开头，后跟小写字母、数字或下划线
    return bool(re.match(r"^[a-z][a-z0-9_]*$", text))

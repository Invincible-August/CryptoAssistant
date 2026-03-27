"""
AI响应解析模块。
负责将大模型返回的文本（可能包含markdown代码块）解析为结构化字典。
包含容错处理，能应对模型输出格式不稳定的情况。
"""
import json
import re
from typing import Any, Dict, Optional

from loguru import logger


def _extract_json_from_text(text: str) -> Optional[str]:
    """
    从可能包含markdown代码块的文本中提取JSON字符串。

    大模型有时会把JSON包裹在 ```json ... ``` 代码块中返回，
    此函数负责剥离这些装饰性标记，提取纯JSON内容。

    解析优先级：
    1. 尝试匹配 ```json ... ``` 代码块
    2. 尝试匹配通用 ``` ... ``` 代码块
    3. 尝试匹配独立的 { ... } JSON对象
    4. 以上都失败则返回原始文本

    Args:
        text: AI模型返回的原始文本

    Returns:
        Optional[str]: 提取出的JSON字符串，提取失败返回None
    """
    if not text or not text.strip():
        return None

    stripped_text = text.strip()

    # 策略1：匹配 ```json ... ``` 格式的代码块（最常见的模型输出格式）
    json_block_pattern = re.compile(
        r"```json\s*\n?(.*?)\n?\s*```",
        re.DOTALL,
    )
    json_block_match = json_block_pattern.search(stripped_text)
    if json_block_match:
        return json_block_match.group(1).strip()

    # 策略2：匹配通用 ``` ... ``` 代码块（部分模型不写json标签）
    generic_block_pattern = re.compile(
        r"```\s*\n?(.*?)\n?\s*```",
        re.DOTALL,
    )
    generic_block_match = generic_block_pattern.search(stripped_text)
    if generic_block_match:
        candidate = generic_block_match.group(1).strip()
        # 验证内容确实像JSON（以 { 开头）
        if candidate.startswith("{"):
            return candidate

    # 策略3：匹配文本中最外层的 { ... } 花括号对
    brace_pattern = re.compile(r"\{.*\}", re.DOTALL)
    brace_match = brace_pattern.search(stripped_text)
    if brace_match:
        return brace_match.group(0).strip()

    # 所有策略都未命中，返回None表示提取失败
    return None


def _safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """
    安全地将文本解析为JSON字典。

    先尝试提取JSON片段，再进行反序列化。
    任何环节失败都返回None而非抛出异常，保证调用方不会因解析错误崩溃。

    Args:
        text: 需要解析的文本

    Returns:
        Optional[Dict[str, Any]]: 解析成功返回字典，失败返回None
    """
    json_str = _extract_json_from_text(text)
    if json_str is None:
        logger.warning("无法从AI响应中提取JSON片段")
        return None

    try:
        parsed = json.loads(json_str)
        # 确保顶层是字典类型，不接受数组或其他类型
        if not isinstance(parsed, dict):
            logger.warning(f"AI响应JSON顶层类型不是对象，实际类型: {type(parsed).__name__}")
            return None
        return parsed
    except json.JSONDecodeError as e:
        logger.warning(f"AI响应JSON解析失败: {e}")
        return None


def parse_analysis_response(response_text: str) -> Dict[str, Any]:
    """
    解析市场综合分析的AI响应。

    从AI返回的文本中提取并解析结构化分析结果，
    包含方向、置信度、入场出场参数、评分、假设、风险等字段。
    解析失败时返回带有错误标记的默认结构。

    Args:
        response_text: AI模型返回的原始文本

    Returns:
        Dict[str, Any]: 结构化分析结果字典，至少包含以下字段：
            - direction: 交易方向
            - confidence: 置信度
            - summary: 分析摘要
            - _parse_error: 是否存在解析错误（仅在失败时出现）
    """
    parsed = _safe_parse_json(response_text)

    if parsed is None:
        # 解析失败：返回中性结果并标记错误，避免上游逻辑中断
        logger.error("市场分析响应解析失败，返回默认中性结果")
        return {
            "direction": "neutral",
            "confidence": 0.0,
            "win_rate": 0.0,
            "entry_zone": None,
            "stop_loss": None,
            "take_profits": [],
            "scores": {},
            "hypotheses": [],
            "evidence": [],
            "risks": ["AI响应解析失败，无法提供可靠分析"],
            "summary": "AI响应解析失败，建议人工分析",
            "_parse_error": True,
            "_raw_text": response_text[:500] if response_text else "",
        }

    # 对关键字段做类型安全处理：确保缺失字段有合理的默认值
    result: Dict[str, Any] = {
        "direction": parsed.get("direction", "neutral"),
        "confidence": _safe_float(parsed.get("confidence"), default=0.0),
        "win_rate": _safe_float(parsed.get("win_rate"), default=0.0),
        "entry_zone": parsed.get("entry_zone"),
        "stop_loss": _safe_float(parsed.get("stop_loss")),
        "take_profits": parsed.get("take_profits", []),
        "scores": parsed.get("scores", {}),
        "hypotheses": parsed.get("hypotheses", []),
        "evidence": parsed.get("evidence", []),
        "risks": parsed.get("risks", []),
        "summary": parsed.get("summary", ""),
    }

    logger.info(f"市场分析响应解析成功，方向: {result['direction']}, 置信度: {result['confidence']}")
    return result


def parse_indicator_suggestion(response_text: str) -> Dict[str, Any]:
    """
    解析AI指标建议的响应。

    从AI返回的文本中提取新指标的定义草案，
    包含指标标识、参数定义、输出定义和计算逻辑。

    Args:
        response_text: AI模型返回的原始文本

    Returns:
        Dict[str, Any]: 指标建议字典，包含indicator_key、name、params_schema等字段。
            解析失败时返回带 _parse_error 标记的空结构。
    """
    parsed = _safe_parse_json(response_text)

    if parsed is None:
        logger.error("指标建议响应解析失败")
        return {
            "indicator_key": "",
            "name": "解析失败",
            "description": "",
            "category": "custom",
            "params_schema": {},
            "output_schema": {},
            "calculation_logic": "",
            "reason": "AI响应解析失败",
            "_parse_error": True,
            "_raw_text": response_text[:500] if response_text else "",
        }

    # 标准化字段：确保每个必要字段都存在
    result: Dict[str, Any] = {
        "indicator_key": parsed.get("indicator_key", ""),
        "name": parsed.get("name", ""),
        "description": parsed.get("description", ""),
        "category": parsed.get("category", "custom"),
        "params_schema": parsed.get("params_schema", {}),
        "output_schema": parsed.get("output_schema", {}),
        "calculation_logic": parsed.get("calculation_logic", ""),
        "reason": parsed.get("reason", ""),
    }

    logger.info(f"指标建议解析成功: {result['indicator_key']} ({result['name']})")
    return result


def parse_factor_suggestion(response_text: str) -> Dict[str, Any]:
    """
    解析AI因子建议的响应。

    从AI返回的文本中提取新因子的定义草案，
    包含因子标识、数据源依赖、参数定义和计算逻辑。

    Args:
        response_text: AI模型返回的原始文本

    Returns:
        Dict[str, Any]: 因子建议字典，包含factor_key、name、input_type等字段。
            解析失败时返回带 _parse_error 标记的空结构。
    """
    parsed = _safe_parse_json(response_text)

    if parsed is None:
        logger.error("因子建议响应解析失败")
        return {
            "factor_key": "",
            "name": "解析失败",
            "description": "",
            "category": "custom",
            "input_type": [],
            "params_schema": {},
            "output_schema": {},
            "score_weight": 1.0,
            "calculation_logic": "",
            "reason": "AI响应解析失败",
            "_parse_error": True,
            "_raw_text": response_text[:500] if response_text else "",
        }

    # 标准化字段：确保每个必要字段都存在
    result: Dict[str, Any] = {
        "factor_key": parsed.get("factor_key", ""),
        "name": parsed.get("name", ""),
        "description": parsed.get("description", ""),
        "category": parsed.get("category", "custom"),
        "input_type": parsed.get("input_type", []),
        "params_schema": parsed.get("params_schema", {}),
        "output_schema": parsed.get("output_schema", {}),
        "score_weight": _safe_float(parsed.get("score_weight"), default=1.0),
        "calculation_logic": parsed.get("calculation_logic", ""),
        "reason": parsed.get("reason", ""),
    }

    logger.info(f"因子建议解析成功: {result['factor_key']} ({result['name']})")
    return result


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    安全地将值转换为浮点数。

    处理AI输出中可能出现的各种非标准数值表示，
    如字符串数字、None等，统一转为float或默认值。

    Args:
        value: 需要转换的值
        default: 转换失败时的默认值

    Returns:
        Optional[float]: 转换结果，失败时返回default
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

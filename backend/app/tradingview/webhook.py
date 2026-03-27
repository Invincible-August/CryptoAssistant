"""
TradingView Webhook接收模块。
负责接收TradingView Alert通过HTTP POST发送的Webhook通知，
执行载荷校验、密钥验证、消息解析，并将结构化信号传递给下游处理器。
"""
import hashlib
import hmac
import json
import re
from typing import Any, Dict, Optional

from loguru import logger


# ==================== Webhook载荷解析 ====================


def validate_webhook_secret(
    payload_body: bytes,
    received_signature: Optional[str],
    webhook_secret: Optional[str],
) -> bool:
    """
    验证Webhook请求的签名是否合法。

    TradingView本身不提供原生的HMAC签名机制，
    但用户可以在Alert消息中附带预共享密钥字段，
    或者通过自定义的HTTP Header传递签名。

    此函数支持两种验证方式：
    1. HMAC-SHA256签名验证（如果配置了webhook_secret且收到了签名）
    2. 跳过验证（如果未配置密钥，则信任所有请求——仅限开发环境）

    Args:
        payload_body: 请求体的原始字节内容
        received_signature: 请求中携带的签名（从Header或载荷字段提取）
        webhook_secret: 本地配置的Webhook密钥

    Returns:
        bool: 签名验证通过返回True，失败返回False
    """
    # 未配置密钥时跳过签名验证（开发环境宽松模式）
    if not webhook_secret:
        logger.warning("Webhook密钥未配置，跳过签名验证（仅限开发环境）")
        return True

    # 配置了密钥但请求中无签名，视为非法请求
    if not received_signature:
        logger.warning("请求中缺少Webhook签名")
        return False

    # 使用HMAC-SHA256计算预期签名
    expected_signature = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # 使用恒定时间比较，防止计时攻击
    is_valid = hmac.compare_digest(expected_signature, received_signature)

    if not is_valid:
        logger.warning("Webhook签名验证失败")
    else:
        logger.debug("Webhook签名验证通过")

    return is_valid


def parse_webhook_payload(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析TradingView Webhook的原始载荷，提取结构化信号数据。

    TradingView Alert的消息格式不固定，用户可以自定义模板。
    此函数支持以下几种常见格式：

    格式1 - JSON结构化消息（推荐）：
    {
        "action": "buy",
        "symbol": "BTCUSDT",
        "price": "65000.5",
        "timeframe": "1h",
        "strategy": "EMA_Cross",
        "secret": "your-webhook-secret"
    }

    格式2 - 纯文本消息（兼容旧版Alert）：
    "BUY BTCUSDT @ 65000.5 1h EMA_Cross"

    Args:
        raw_payload: HTTP请求体解析后的字典（或包含"message"键的字典）

    Returns:
        Dict[str, Any]: 标准化后的信号数据字典，至少包含：
            - action: 交易动作（buy / sell / close / 空字符串）
            - symbol: 交易对名称（大写）
            - price: 触发价格（字符串）
            - timeframe: 时间周期
            - strategy: 策略名称
            - raw: 原始载荷的副本
    """
    # 如果载荷包含message字段，可能是TradingView的纯文本消息模式
    message_text = raw_payload.get("message", "")

    # 情况1：载荷本身已经是结构化的JSON
    if "action" in raw_payload:
        signal = _normalize_structured_payload(raw_payload)
        logger.info(f"解析结构化Webhook载荷: action={signal.get('action')}, symbol={signal.get('symbol')}")
        return signal

    # 情况2：通过message字段传递的纯文本消息
    if message_text:
        signal = _parse_text_message(message_text)
        signal["raw"] = raw_payload
        logger.info(f"解析文本Webhook消息: action={signal.get('action')}, symbol={signal.get('symbol')}")
        return signal

    # 情况3：无法识别的格式，原样返回并标记为未知
    logger.warning(f"无法识别的Webhook载荷格式: {raw_payload}")
    return {
        "action": "",
        "symbol": "",
        "price": "",
        "timeframe": "",
        "strategy": "",
        "raw": raw_payload,
        "_parse_warning": "无法识别的载荷格式",
    }


def _normalize_structured_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    标准化结构化JSON载荷的字段格式。

    将用户在TradingView Alert中自定义的JSON字段映射到
    系统内部统一的信号字段名称，并做基础的数据清洗。

    Args:
        payload: 原始JSON载荷字典

    Returns:
        Dict[str, Any]: 标准化后的信号字典
    """
    # action字段标准化：统一转为小写
    raw_action = str(payload.get("action", "")).strip().lower()

    # 将常见的中英文同义动作统一映射
    action_mapping: Dict[str, str] = {
        "buy": "buy",
        "long": "buy",
        "做多": "buy",
        "买入": "buy",
        "sell": "sell",
        "short": "sell",
        "做空": "sell",
        "卖出": "sell",
        "close": "close",
        "平仓": "close",
        "exit": "close",
    }
    normalized_action = action_mapping.get(raw_action, raw_action)

    # symbol字段标准化：统一转为大写，移除可能的斜杠分隔符
    raw_symbol = str(payload.get("symbol", payload.get("ticker", ""))).strip().upper()
    normalized_symbol = raw_symbol.replace("/", "").replace("-", "")

    return {
        "action": normalized_action,
        "symbol": normalized_symbol,
        "price": str(payload.get("price", payload.get("close", ""))),
        "timeframe": str(payload.get("timeframe", payload.get("interval", ""))),
        "strategy": str(payload.get("strategy", payload.get("strategy_name", ""))),
        "quantity": str(payload.get("quantity", payload.get("qty", ""))),
        "stop_loss": str(payload.get("stop_loss", payload.get("sl", ""))),
        "take_profit": str(payload.get("take_profit", payload.get("tp", ""))),
        "comment": str(payload.get("comment", payload.get("message", ""))),
        "raw": payload,
    }


def _parse_text_message(message: str) -> Dict[str, Any]:
    """
    解析TradingView纯文本格式的Alert消息。

    支持的文本格式示例：
    - "BUY BTCUSDT @ 65000.5 1h EMA_Cross"
    - "SELL ETH/USDT 3500.0 4h RSI_Divergence"
    - "CLOSE BTCUSDT"

    使用正则表达式匹配关键字段，对无法匹配的部分给出合理的默认值。

    Args:
        message: TradingView Alert的纯文本消息

    Returns:
        Dict[str, Any]: 从文本中提取的信号字段
    """
    cleaned_message = message.strip()

    # 正则模式：动作 + 交易对 + 可选的价格和其他信息
    # 示例匹配: "BUY BTCUSDT @ 65000.5 1h EMA_Cross"
    pattern = re.compile(
        r"^(BUY|SELL|LONG|SHORT|CLOSE|EXIT)"  # 动作关键词（大写）
        r"\s+"
        r"([A-Z0-9/\-]+)"                     # 交易对（字母+数字，可含/和-）
        r"(?:\s+@?\s*(\d+\.?\d*))?"            # 可选的价格（@前缀可选）
        r"(?:\s+(\w+))?"                       # 可选的时间周期
        r"(?:\s+(.+))?"                        # 可选的策略名称（余下所有内容）
        r"$",
        re.IGNORECASE,
    )

    match = pattern.match(cleaned_message)

    if match:
        # 正则匹配成功，提取各分组
        action_raw = match.group(1).lower()
        symbol_raw = match.group(2).upper().replace("/", "").replace("-", "")
        price = match.group(3) or ""
        timeframe = match.group(4) or ""
        strategy = match.group(5) or ""

        # 动作同义词映射
        action_mapping = {
            "buy": "buy", "long": "buy",
            "sell": "sell", "short": "sell",
            "close": "close", "exit": "close",
        }

        return {
            "action": action_mapping.get(action_raw, action_raw),
            "symbol": symbol_raw,
            "price": price,
            "timeframe": timeframe,
            "strategy": strategy.strip(),
            "quantity": "",
            "stop_loss": "",
            "take_profit": "",
            "comment": "",
        }

    # 正则匹配失败，尝试简单的空格分词提取
    logger.warning(f"纯文本消息正则匹配失败，尝试分词提取: {cleaned_message}")
    tokens = cleaned_message.split()

    return {
        "action": tokens[0].lower() if len(tokens) > 0 else "",
        "symbol": tokens[1].upper() if len(tokens) > 1 else "",
        "price": tokens[2] if len(tokens) > 2 else "",
        "timeframe": tokens[3] if len(tokens) > 3 else "",
        "strategy": " ".join(tokens[4:]) if len(tokens) > 4 else "",
        "quantity": "",
        "stop_loss": "",
        "take_profit": "",
        "comment": "",
    }

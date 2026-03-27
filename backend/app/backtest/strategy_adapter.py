"""
策略适配器模块。
将不同格式的策略配置适配为回测引擎可用的标准格式。
"""
from typing import Any, Dict, List


# 默认策略配置
DEFAULT_STRATEGY_CONFIG = {
    "warmup_period": 60,
    "entry_threshold": 65,
    "exit_threshold": 35,
    "position_size": 0.1,
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.04,
    "indicators": ["ema", "rsi", "macd"],
    "factors": ["momentum", "volatility"],
}


def adapt_strategy_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    将用户传入的策略配置适配为引擎内部格式。
    缺失字段使用默认值补全。

    Args:
        raw_config: 用户传入的原始配置

    Returns:
        标准化后的策略配置
    """
    config = DEFAULT_STRATEGY_CONFIG.copy()

    for key in DEFAULT_STRATEGY_CONFIG:
        if key in raw_config:
            config[key] = raw_config[key]

    # 确保数值在合理范围内
    config["warmup_period"] = max(10, min(500, config["warmup_period"]))
    config["position_size"] = max(0.01, min(1.0, config["position_size"]))
    config["stop_loss_pct"] = max(0.001, min(0.2, config["stop_loss_pct"]))
    config["take_profit_pct"] = max(0.001, min(0.5, config["take_profit_pct"]))

    return config


def get_strategy_indicators(config: Dict[str, Any]) -> List[str]:
    """从策略配置中提取需要的指标列表"""
    return config.get("indicators", DEFAULT_STRATEGY_CONFIG["indicators"])


def get_strategy_factors(config: Dict[str, Any]) -> List[str]:
    """从策略配置中提取需要的因子列表"""
    return config.get("factors", DEFAULT_STRATEGY_CONFIG["factors"])

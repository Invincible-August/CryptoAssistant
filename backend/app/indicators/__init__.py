"""
指标插件包。
初始化时自动注册所有内置指标和自定义指标。
"""
from app.indicators.registry import indicator_registry


def register_all_indicators() -> None:
    """
    注册所有指标插件（内置 + 自定义）。

    该函数在应用启动时调用，自动扫描 builtins/ 和 custom/ 目录下的
    所有指标模块，将发现的指标类注册到全局注册中心。

    调用顺序：
    1. 先扫描 builtins/ 目录 → 注册系统内置指标（MA、EMA、RSI等）
    2. 再扫描 custom/ 目录 → 注册用户自定义指标（volume_spike等）
    """
    # 自动扫描并注册内置指标目录下的所有指标
    indicator_registry.auto_discover(
        "app/indicators/builtins",
        "app.indicators.builtins"
    )
    # 自动扫描并注册自定义指标目录下的所有指标
    indicator_registry.auto_discover(
        "app/indicators/custom",
        "app.indicators.custom"
    )

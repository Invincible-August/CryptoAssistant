"""
数学工具模块。
提供价格精度处理、盈亏计算等通用数学函数。
"""
from decimal import Decimal, ROUND_DOWN


def round_price(price: float, tick_size: float) -> Decimal:
    """按照最小价格变动单位取整"""
    d_price = Decimal(str(price))
    d_tick = Decimal(str(tick_size))
    return (d_price / d_tick).quantize(Decimal("1"), rounding=ROUND_DOWN) * d_tick


def round_quantity(qty: float, step_size: float) -> Decimal:
    """按照最小数量步长取整"""
    d_qty = Decimal(str(qty))
    d_step = Decimal(str(step_size))
    return (d_qty / d_step).quantize(Decimal("1"), rounding=ROUND_DOWN) * d_step


def calculate_pnl(
    entry_price: float,
    exit_price: float,
    quantity: float,
    direction: str,
) -> float:
    """计算盈亏金额"""
    if direction == "long":
        return (exit_price - entry_price) * quantity
    else:
        return (entry_price - exit_price) * quantity


def percentage_change(old_value: float, new_value: float) -> float:
    """计算百分比变化"""
    if old_value == 0:
        return 0.0
    return (new_value - old_value) / old_value


def clamp(value: float, min_val: float, max_val: float) -> float:
    """将值限制在指定范围内"""
    return max(min_val, min(max_val, value))

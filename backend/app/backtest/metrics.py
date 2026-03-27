"""
回测绩效指标计算模块。
计算收益率、最大回撤、胜率、夏普比率等核心指标。
"""
from typing import Any, Dict, List
from datetime import datetime
import math


def calculate_metrics(
    trades: List[Dict[str, Any]],
    initial_capital: float,
    equity_curve: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    计算回测绩效指标。

    Args:
        trades: 交易记录列表
        initial_capital: 初始资金
        equity_curve: 净值曲线

    Returns:
        包含所有绩效指标的字典
    """
    if not trades:
        return {
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "profit_loss_ratio": 0.0,
            "total_trades": 0,
            "avg_holding_time": 0.0,
            "sharpe_ratio": 0.0,
        }

    # 总收益率
    final_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital

    # 最大回撤
    max_drawdown = _calculate_max_drawdown(equity_curve)

    # 胜率
    winning_trades = [t for t in trades if t.get("pnl", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl", 0) <= 0]
    win_rate = len(winning_trades) / len(trades) if trades else 0.0

    # 盈亏比
    avg_win = (
        sum(t["pnl"] for t in winning_trades) / len(winning_trades)
        if winning_trades
        else 0.0
    )
    avg_loss = (
        abs(sum(t["pnl"] for t in losing_trades) / len(losing_trades))
        if losing_trades
        else 1.0
    )
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else float("inf")

    # 平均持仓时间（小时）
    avg_holding_time = _calculate_avg_holding_time(trades)

    # 夏普比率（简化版，基于净值曲线日收益率）
    sharpe_ratio = _calculate_sharpe_ratio(equity_curve)

    return {
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_drawdown, 4),
        "win_rate": round(win_rate, 4),
        "profit_loss_ratio": round(profit_loss_ratio, 4),
        "total_trades": len(trades),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "avg_holding_time": round(avg_holding_time, 2),
        "sharpe_ratio": round(sharpe_ratio, 4),
        "total_pnl": round(sum(t.get("pnl", 0) for t in trades), 4),
        "avg_pnl": round(
            sum(t.get("pnl", 0) for t in trades) / len(trades), 4
        ),
        "final_equity": round(final_equity, 2),
        "initial_capital": initial_capital,
    }


def _calculate_max_drawdown(equity_curve: List[Dict[str, Any]]) -> float:
    """计算最大回撤"""
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]["equity"]
    max_dd = 0.0

    for point in equity_curve:
        equity = point["equity"]
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, drawdown)

    return max_dd


def _calculate_avg_holding_time(trades: List[Dict[str, Any]]) -> float:
    """计算平均持仓时间（小时）"""
    if not trades:
        return 0.0

    total_hours = 0.0
    valid_count = 0

    for trade in trades:
        try:
            entry_str = trade.get("entry_time", "")
            exit_str = trade.get("exit_time", "")
            if not entry_str or not exit_str:
                continue

            entry_time = _parse_time(entry_str)
            exit_time = _parse_time(exit_str)

            if entry_time and exit_time:
                delta = (exit_time - entry_time).total_seconds() / 3600.0
                total_hours += delta
                valid_count += 1
        except Exception:
            continue

    return total_hours / valid_count if valid_count > 0 else 0.0


def _calculate_sharpe_ratio(
    equity_curve: List[Dict[str, Any]],
    risk_free_rate: float = 0.0,
    annualize_factor: float = 365.0,
) -> float:
    """
    计算夏普比率（简化版）。
    基于净值曲线的逐期收益率。
    """
    if len(equity_curve) < 2:
        return 0.0

    # 计算逐期收益率
    returns = []
    for i in range(1, len(equity_curve)):
        prev_eq = equity_curve[i - 1]["equity"]
        curr_eq = equity_curve[i]["equity"]
        if prev_eq > 0:
            ret = (curr_eq - prev_eq) / prev_eq
            returns.append(ret)

    if not returns:
        return 0.0

    # 均值和标准差
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_return = math.sqrt(variance) if variance > 0 else 0.0

    if std_return == 0:
        return 0.0

    # 年化夏普比率
    sharpe = (mean_return - risk_free_rate / annualize_factor) / std_return
    sharpe *= math.sqrt(annualize_factor)

    return sharpe


def _parse_time(time_str: str) -> datetime:
    """尝试解析时间字符串"""
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return None

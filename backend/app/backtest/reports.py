"""
回测报告生成模块。
生成中文文本报告和格式化的图表数据。
"""
from typing import Any, Dict, List


def generate_text_report(result: Dict[str, Any]) -> str:
    """
    生成中文文本格式的回测报告。

    Args:
        result: 回测结果（包含metrics, trades, equity_curve）

    Returns:
        中文报告文本
    """
    metrics = result.get("metrics", {})
    trades = result.get("trades", [])

    lines = [
        "=" * 50,
        "         回测绩效报告",
        "=" * 50,
        "",
        f"初始资金:     {metrics.get('initial_capital', 0):,.2f} USDT",
        f"最终净值:     {metrics.get('final_equity', 0):,.2f} USDT",
        f"总收益率:     {metrics.get('total_return', 0):.2%}",
        f"最大回撤:     {metrics.get('max_drawdown', 0):.2%}",
        f"夏普比率:     {metrics.get('sharpe_ratio', 0):.4f}",
        "",
        f"总交易次数:   {metrics.get('total_trades', 0)}",
        f"盈利次数:     {metrics.get('winning_trades', 0)}",
        f"亏损次数:     {metrics.get('losing_trades', 0)}",
        f"胜率:         {metrics.get('win_rate', 0):.2%}",
        f"盈亏比:       {metrics.get('profit_loss_ratio', 0):.4f}",
        f"平均盈亏:     {metrics.get('avg_pnl', 0):,.4f} USDT",
        f"总盈亏:       {metrics.get('total_pnl', 0):,.4f} USDT",
        f"平均持仓时间: {metrics.get('avg_holding_time', 0):.2f} 小时",
        "",
    ]

    if trades:
        lines.append("-" * 50)
        lines.append("最近5笔交易:")
        lines.append("-" * 50)
        for trade in trades[-5:]:
            direction = "多" if trade.get("direction") == "long" else "空"
            pnl = trade.get("pnl", 0)
            pnl_str = f"+{pnl:.4f}" if pnl > 0 else f"{pnl:.4f}"
            lines.append(
                f"  {direction} | "
                f"入场 {trade.get('entry_price', 0):.4f} → "
                f"出场 {trade.get('exit_price', 0):.4f} | "
                f"盈亏 {pnl_str}"
            )

    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


def format_trades_for_api(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """格式化交易记录供API返回"""
    formatted = []
    for i, trade in enumerate(trades):
        formatted.append(
            {
                "index": i + 1,
                "direction": trade.get("direction", ""),
                "entry_time": trade.get("entry_time", ""),
                "exit_time": trade.get("exit_time", ""),
                "entry_price": trade.get("entry_price", 0),
                "exit_price": trade.get("exit_price", 0),
                "quantity": trade.get("quantity", 0),
                "pnl": trade.get("pnl", 0),
                "pnl_ratio": trade.get("pnl_ratio", 0),
                "reason": trade.get("reason", ""),
            }
        )
    return formatted


def format_equity_curve_for_chart(
    equity_curve: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """格式化净值曲线供前端图表展示"""
    return [
        {
            "time": point.get("time", ""),
            "equity": round(point.get("equity", 0), 2),
            "price": round(point.get("price", 0), 8),
        }
        for point in equity_curve
    ]

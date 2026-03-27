"""
交易模拟器模块。
模拟真实交易环境中的下单、持仓、止盈止损等逻辑。
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from loguru import logger


class Position:
    """持仓对象"""

    def __init__(
        self,
        direction: str,
        entry_price: float,
        quantity: float,
        entry_time: datetime,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        reason: str = "",
    ):
        self.direction = direction
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.reason = reason


class TradeSimulator:
    """
    交易模拟器。
    管理虚拟资金、持仓、手续费和滑点。
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        fee_rate: float = 0.001,
        slippage: float = 0.0005,
    ):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.position: Optional[Position] = None
        self.trade_history: List[Dict[str, Any]] = []

    def get_current_position(self) -> Optional[Position]:
        """获取当前持仓"""
        return self.position

    def get_equity(self, current_price: float) -> float:
        """计算当前净值（含浮动盈亏）"""
        if self.position is None:
            return self.capital

        unrealized_pnl = self._calc_pnl(
            self.position.entry_price,
            current_price,
            self.position.quantity,
            self.position.direction,
        )
        return self.capital + unrealized_pnl

    def process_signal(
        self,
        signal: Dict[str, Any],
        current_price: float,
        current_time: datetime,
    ) -> Optional[Dict[str, Any]]:
        """
        处理交易信号，开仓。

        Args:
            signal: 包含 direction, size_ratio, stop_loss, take_profit, reason
            current_price: 当前价格
            current_time: 当前时间

        Returns:
            成交记录或None
        """
        # 已有持仓则跳过
        if self.position is not None:
            return None

        direction = signal.get("direction", "long")
        size_ratio = signal.get("size_ratio", 0.1)
        stop_loss = signal.get("stop_loss", 0.0)
        take_profit = signal.get("take_profit", 0.0)
        reason = signal.get("reason", "")

        # 计算滑点后的实际入场价
        if direction == "long":
            fill_price = current_price * (1 + self.slippage)
        else:
            fill_price = current_price * (1 - self.slippage)

        # 计算可用资金和数量
        available = self.capital * size_ratio
        fee = available * self.fee_rate
        quantity = (available - fee) / fill_price

        if quantity <= 0:
            return None

        # 扣除保证金（简化为全额占用）
        self.capital -= available

        self.position = Position(
            direction=direction,
            entry_price=fill_price,
            quantity=quantity,
            entry_time=current_time,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
        )

        logger.debug(
            f"开仓: {direction} @ {fill_price:.4f}, 数量={quantity:.6f}, 原因={reason}"
        )
        return None

    def check_exits(
        self,
        current_price: float,
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """检查止盈止损条件"""
        closed_trades = []
        if self.position is None:
            return closed_trades

        should_close = False
        close_reason = ""

        if self.position.direction == "long":
            # 多头止损
            if self.position.stop_loss > 0 and current_price <= self.position.stop_loss:
                should_close = True
                close_reason = f"触发止损: 价格{current_price:.4f} <= 止损{self.position.stop_loss:.4f}"
            # 多头止盈
            elif self.position.take_profit > 0 and current_price >= self.position.take_profit:
                should_close = True
                close_reason = f"触发止盈: 价格{current_price:.4f} >= 止盈{self.position.take_profit:.4f}"
        else:
            # 空头止损
            if self.position.stop_loss > 0 and current_price >= self.position.stop_loss:
                should_close = True
                close_reason = f"触发止损: 价格{current_price:.4f} >= 止损{self.position.stop_loss:.4f}"
            # 空头止盈
            elif self.position.take_profit > 0 and current_price <= self.position.take_profit:
                should_close = True
                close_reason = f"触发止盈: 价格{current_price:.4f} <= 止盈{self.position.take_profit:.4f}"

        if should_close:
            trade = self._close_position(current_price, current_time, close_reason)
            if trade:
                closed_trades.append(trade)

        return closed_trades

    def close_all(
        self,
        current_price: float,
        current_time: datetime,
    ) -> List[Dict[str, Any]]:
        """平掉所有持仓"""
        trades = []
        if self.position is not None:
            trade = self._close_position(current_price, current_time, "回测结束强制平仓")
            if trade:
                trades.append(trade)
        return trades

    def _close_position(
        self,
        exit_price: float,
        exit_time: datetime,
        reason: str,
    ) -> Optional[Dict[str, Any]]:
        """内部平仓方法"""
        if self.position is None:
            return None

        # 计算滑点后的实际出场价
        if self.position.direction == "long":
            fill_price = exit_price * (1 - self.slippage)
        else:
            fill_price = exit_price * (1 + self.slippage)

        # 计算盈亏
        pnl = self._calc_pnl(
            self.position.entry_price,
            fill_price,
            self.position.quantity,
            self.position.direction,
        )
        fee = abs(fill_price * self.position.quantity * self.fee_rate)
        net_pnl = pnl - fee

        # 归还资金
        position_value = self.position.entry_price * self.position.quantity
        self.capital += position_value + net_pnl

        # 计算收益率
        pnl_ratio = net_pnl / position_value if position_value > 0 else 0.0

        trade_record = {
            "direction": self.position.direction,
            "entry_time": str(self.position.entry_time),
            "exit_time": str(exit_time),
            "entry_price": round(self.position.entry_price, 8),
            "exit_price": round(fill_price, 8),
            "quantity": round(self.position.quantity, 8),
            "pnl": round(net_pnl, 4),
            "pnl_ratio": round(pnl_ratio, 6),
            "reason": f"开仓: {self.position.reason} | 平仓: {reason}",
        }

        self.trade_history.append(trade_record)
        self.position = None

        logger.debug(f"平仓: PnL={net_pnl:.4f}, 原因={reason}")
        return trade_record

    @staticmethod
    def _calc_pnl(
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

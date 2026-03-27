"""
回测模块单元测试。
"""
import pytest
from app.backtest.simulator import TradeSimulator
from app.backtest.metrics import calculate_metrics
from datetime import datetime


class TestTradeSimulator:
    """测试交易模拟器"""

    def test_initial_state(self):
        """初始状态"""
        sim = TradeSimulator(initial_capital=10000)
        assert sim.capital == 10000
        assert sim.get_current_position() is None

    def test_open_long(self):
        """开多仓"""
        sim = TradeSimulator(initial_capital=10000, slippage=0)
        signal = {
            "direction": "long",
            "size_ratio": 0.1,
            "stop_loss": 60000,
            "take_profit": 70000,
        }
        sim.process_signal(signal, 65000, datetime(2024, 1, 1))
        assert sim.get_current_position() is not None
        assert sim.get_current_position().direction == "long"

    def test_stop_loss(self):
        """止损触发"""
        sim = TradeSimulator(initial_capital=10000, slippage=0, fee_rate=0)
        signal = {
            "direction": "long",
            "size_ratio": 0.1,
            "stop_loss": 60000,
            "take_profit": 70000,
        }
        sim.process_signal(signal, 65000, datetime(2024, 1, 1))
        trades = sim.check_exits(59000, datetime(2024, 1, 2))
        assert len(trades) == 1
        assert trades[0]["pnl"] < 0

    def test_equity_calculation(self):
        """净值计算"""
        sim = TradeSimulator(initial_capital=10000, slippage=0, fee_rate=0)
        equity = sim.get_equity(65000)
        assert equity == 10000


class TestMetrics:
    """测试绩效指标计算"""

    def test_empty_trades(self):
        """空交易列表"""
        result = calculate_metrics([], 10000, [])
        assert result["total_trades"] == 0
        assert result["total_return"] == 0

    def test_with_trades(self):
        """含交易记录"""
        trades = [
            {"pnl": 100, "entry_time": "2024-01-01 00:00:00", "exit_time": "2024-01-02 00:00:00"},
            {"pnl": -50, "entry_time": "2024-01-03 00:00:00", "exit_time": "2024-01-04 00:00:00"},
        ]
        equity = [
            {"equity": 10000, "price": 65000},
            {"equity": 10100, "price": 65500},
            {"equity": 10050, "price": 65200},
        ]
        result = calculate_metrics(trades, 10000, equity)
        assert result["total_trades"] == 2
        assert result["winning_trades"] == 1
        assert result["losing_trades"] == 1

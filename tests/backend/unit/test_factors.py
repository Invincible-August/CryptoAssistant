"""
因子单元测试。
测试所有内置因子和自定义因子的计算逻辑。
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _make_context(n: int = 100) -> dict:
    """生成测试用因子上下文"""
    dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
    np.random.seed(42)
    base = 65000.0
    prices = [base]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.01)))

    kline_df = pd.DataFrame({
        "open_time": dates,
        "open": prices,
        "high": [p * 1.005 for p in prices],
        "low": [p * 0.995 for p in prices],
        "close": [p * (1 + np.random.normal(0, 0.002)) for p in prices],
        "volume": np.random.uniform(100, 5000, n),
    })

    return {"kline": kline_df}


class TestMomentumFactor:
    """测试动量因子"""

    def test_calculate(self):
        """动量因子计算结果"""
        from app.factors.builtins.momentum_factor import MomentumFactor
        context = _make_context()
        result = MomentumFactor.calculate(context, {})
        assert "factor_key" in result
        assert result["factor_key"] == "momentum"

    def test_normalize(self):
        """归一化结果包含score字段"""
        from app.factors.builtins.momentum_factor import MomentumFactor
        context = _make_context()
        result = MomentumFactor.calculate(context, {})
        normalized = MomentumFactor.normalize(result)
        assert "score" in normalized


class TestMainForceCostZoneFactor:
    """测试主力成本区间因子"""

    def test_calculate(self):
        """成本区间因子计算"""
        from app.factors.custom.main_force_cost_zone_factor import MainForceCostZoneFactor
        context = _make_context()
        result = MainForceCostZoneFactor.calculate(context, {})
        assert "vwap" in result
        assert "cost_zone_low" in result
        assert "cost_zone_high" in result
        assert "cost_advantage_score" in result

    def test_source_is_human(self):
        """来源标记为human"""
        from app.factors.custom.main_force_cost_zone_factor import MainForceCostZoneFactor
        meta = MainForceCostZoneFactor.get_metadata()
        assert meta["source"] == "human"

    def test_format_for_signal(self):
        """信号格式转换"""
        from app.factors.custom.main_force_cost_zone_factor import MainForceCostZoneFactor
        context = _make_context()
        result = MainForceCostZoneFactor.calculate(context, {})
        signal = MainForceCostZoneFactor.format_for_signal(result)
        assert "factor_key" in signal
        assert "signal_value" in signal


class TestFactorRegistry:
    """测试因子注册中心"""

    def test_register_and_get(self):
        """注册和获取因子"""
        from app.factors.registry import FactorRegistry
        from app.factors.builtins.momentum_factor import MomentumFactor

        registry = FactorRegistry()
        registry.register(MomentumFactor)
        cls = registry.get("momentum")
        assert cls is MomentumFactor

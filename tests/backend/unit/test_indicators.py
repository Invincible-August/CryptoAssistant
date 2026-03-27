"""
指标单元测试。
测试所有内置指标和自定义指标的计算逻辑。
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def _make_kline_df(n: int = 100) -> pd.DataFrame:
    """生成测试用K线数据"""
    dates = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
    np.random.seed(42)
    base = 65000.0
    prices = [base]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.01)))

    return pd.DataFrame({
        "open_time": dates,
        "open": prices,
        "high": [p * 1.005 for p in prices],
        "low": [p * 0.995 for p in prices],
        "close": [p * (1 + np.random.normal(0, 0.002)) for p in prices],
        "volume": np.random.uniform(100, 5000, n),
    })


class TestMAIndicator:
    """测试简单移动平均线指标"""

    def test_calculate_default(self):
        """默认参数计算"""
        from app.indicators.builtins.ma import MAIndicator
        df = _make_kline_df()
        result = MAIndicator.calculate(df, {})
        assert "ma_20" in result.columns
        assert len(result) == len(df)

    def test_metadata(self):
        """指标元数据完整性"""
        from app.indicators.builtins.ma import MAIndicator
        meta = MAIndicator.get_metadata()
        assert meta["indicator_key"] == "ma"
        assert meta["source"] == "system"
        assert meta["category"] == "trend"


class TestRSIIndicator:
    """测试RSI指标"""

    def test_calculate(self):
        """RSI计算结果在0-100范围内"""
        from app.indicators.builtins.rsi import RSIIndicator
        df = _make_kline_df()
        result = RSIIndicator.calculate(df, {})
        assert "rsi" in result.columns
        valid_rsi = result["rsi"].dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()


class TestMACDIndicator:
    """测试MACD指标"""

    def test_calculate(self):
        """MACD三线计算"""
        from app.indicators.builtins.macd import MACDIndicator
        df = _make_kline_df()
        result = MACDIndicator.calculate(df, {})
        assert "dif" in result.columns
        assert "dea" in result.columns
        assert "macd_hist" in result.columns


class TestVolumeSpikeIndicator:
    """测试自定义成交量脉冲指标"""

    def test_calculate(self):
        """成交量脉冲检测"""
        from app.indicators.custom.volume_spike import VolumeSpikeIndicator
        df = _make_kline_df()
        result = VolumeSpikeIndicator.calculate(df, {})
        assert "volume_ratio" in result.columns
        assert "is_spike" in result.columns

    def test_metadata(self):
        """来源标记为human"""
        from app.indicators.custom.volume_spike import VolumeSpikeIndicator
        meta = VolumeSpikeIndicator.get_metadata()
        assert meta["source"] == "human"


class TestIndicatorRegistry:
    """测试指标注册中心"""

    def test_register_and_get(self):
        """注册和获取指标"""
        from app.indicators.registry import IndicatorRegistry
        from app.indicators.builtins.ma import MAIndicator

        registry = IndicatorRegistry()
        registry.register(MAIndicator)
        cls = registry.get("ma")
        assert cls is MAIndicator

    def test_list_all(self):
        """列出所有指标"""
        from app.indicators.registry import IndicatorRegistry
        from app.indicators.builtins.ma import MAIndicator
        from app.indicators.builtins.rsi import RSIIndicator

        registry = IndicatorRegistry()
        registry.register(MAIndicator)
        registry.register(RSIIndicator)
        all_meta = registry.list_all()
        assert len(all_meta) == 2

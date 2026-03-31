"""
波动率因子模块。
基于K线数据计算ATR、布林带宽度和历史波动率，
综合输出波动率评分，用于衡量市场波动程度和风险水平。
"""
import math
from typing import Any, Dict, List

from app.factors.base import BaseFactor


class VolatilityFactor(BaseFactor):
    """
    波动率因子。

    计算逻辑：
    1. ATR（Average True Range）：平均真实波幅，衡量绝对波动
    2. 布林带宽度（BB Width）：(上轨-下轨)/中轨，衡量相对波动
    3. 历史波动率（Historical Volatility）：收益率的标准差年化值
    4. 综合评分：加权合成以上三个维度，映射到 0-100 区间
    """

    factor_key: str = "volatility"
    name: str = "波动率因子"
    description: str = "计算ATR、布林带宽度和历史波动率，综合评估市场波动程度"
    source: str = "system"
    version: str = "1.0.0"
    category: str = "volatility"
    input_type: List[str] = ["kline"]
    score_weight: float = 1.0
    signal_compatible: bool = True
    backtest_compatible: bool = True
    ai_compatible: bool = True

    # ==================== 参数定义 ====================
    params_schema: Dict[str, Any] = {
        "atr_period": {
            "type": "int",
            "default": 14,
            "required": False,
            "description": "ATR计算周期",
            "min": 2,
            "max": 200,
        },
        "bb_period": {
            "type": "int",
            "default": 20,
            "required": False,
            "description": "布林带计算周期（中轨SMA周期）",
            "min": 5,
            "max": 200,
        },
        "bb_std_multiplier": {
            "type": "float",
            "default": 2.0,
            "required": False,
            "description": "布林带标准差倍数",
            "min": 0.5,
            "max": 5.0,
        },
        "hv_period": {
            "type": "int",
            "default": 20,
            "required": False,
            "description": "历史波动率计算周期",
            "min": 5,
            "max": 200,
        },
    }

    # ==================== 输出字段定义 ====================
    output_schema: Dict[str, Any] = {
        "atr": {
            "type": "float",
            "description": "平均真实波幅（绝对值）",
        },
        "bb_width": {
            "type": "float",
            "description": "布林带宽度（相对值，百分比）",
        },
        "historical_volatility": {
            "type": "float",
            "description": "历史波动率（年化百分比）",
        },
        "volatility_score": {
            "type": "float",
            "description": "综合波动率评分（0-100），分数越高波动越剧烈",
        },
    }

    # ==================== 前端展示配置 ====================
    display_config: Dict[str, Any] = {
        "chart_type": "line",
        "primary_field": "volatility_score",
        "overlay": False,
        "color": "#E74C3C",
        "y_axis_label": "波动率评分",
    }

    @classmethod
    def calculate(cls, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算波动率因子。

        Args:
            context: 数据上下文，需包含 "kline" 键。
                     每根K线需包含 high、low、close 字段。
            params:  参数字典，支持 atr_period、bb_period、bb_std_multiplier、hv_period。

        Returns:
            Dict[str, Any]: 包含 atr、bb_width、historical_volatility、volatility_score
        """
        # ---------- 参数校验 ----------
        validated_params = cls.validate_params(params)
        atr_period: int = validated_params["atr_period"]
        bb_period: int = validated_params["bb_period"]
        bb_std_multiplier: float = validated_params["bb_std_multiplier"]
        hv_period: int = validated_params["hv_period"]

        # ---------- 获取K线数据 ----------
        kline_data: List[Dict[str, Any]] = context.get("kline", [])

        # 兼容：FeaturePipeline/单测可能传入 pandas.DataFrame
        try:
            import pandas as pd  # type: ignore

            if isinstance(kline_data, pd.DataFrame):
                kline_data = kline_data.to_dict("records")  # type: ignore[assignment]
        except Exception:  # noqa: BLE001
            pass

        # 需要的最小K线数量取各参数周期的最大值加1
        min_required = max(atr_period, bb_period, hv_period) + 1
        if len(kline_data) < min_required:
            return {
                "atr": 0.0,
                "bb_width": 0.0,
                "historical_volatility": 0.0,
                "volatility_score": 50.0,
            }

        # 提取 OHLC 数据
        high_prices: List[float] = [float(c["high"]) for c in kline_data]
        low_prices: List[float] = [float(c["low"]) for c in kline_data]
        close_prices: List[float] = [float(c["close"]) for c in kline_data]

        # ---------- 1. 计算 ATR（平均真实波幅） ----------
        atr = cls._calculate_atr(high_prices, low_prices, close_prices, atr_period)

        # ---------- 2. 计算布林带宽度 ----------
        bb_width = cls._calculate_bb_width(close_prices, bb_period, bb_std_multiplier)

        # ---------- 3. 计算历史波动率 ----------
        historical_volatility = cls._calculate_historical_volatility(
            close_prices, hv_period
        )

        # ---------- 4. 综合波动率评分 ----------
        volatility_score = cls._compute_volatility_score(
            atr=atr,
            bb_width=bb_width,
            historical_volatility=historical_volatility,
            current_price=close_prices[-1],
        )

        return {
            "atr": round(atr, 6),
            "bb_width": round(bb_width, 4),
            "historical_volatility": round(historical_volatility, 4),
            "volatility_score": round(volatility_score, 2),
        }

    @classmethod
    def _calculate_atr(
        cls,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int,
    ) -> float:
        """
        计算 ATR（Average True Range）。

        真实波幅 TR 取以下三者的最大值：
        - 当日最高价 - 当日最低价
        - |当日最高价 - 前日收盘价|
        - |当日最低价 - 前日收盘价|

        ATR = TR 在 period 周期内的简单移动平均

        Args:
            highs:  最高价序列
            lows:   最低价序列
            closes: 收盘价序列
            period: ATR计算周期

        Returns:
            float: ATR值
        """
        true_ranges: List[float] = []
        for i in range(1, len(highs)):
            # 三种真实波幅的定义
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i - 1])
            tr3 = abs(lows[i] - closes[i - 1])
            true_ranges.append(max(tr1, tr2, tr3))

        # 取最近 period 个 TR 求平均
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

        recent_trs = true_ranges[-period:]
        return sum(recent_trs) / period

    @classmethod
    def _calculate_bb_width(
        cls,
        closes: List[float],
        period: int,
        std_multiplier: float,
    ) -> float:
        """
        计算布林带宽度。

        布林带：
        - 中轨 = SMA(close, period)
        - 上轨 = 中轨 + std_multiplier * StdDev(close, period)
        - 下轨 = 中轨 - std_multiplier * StdDev(close, period)
        - 宽度 = (上轨 - 下轨) / 中轨 * 100（百分比）

        Args:
            closes:         收盘价序列
            period:         布林带周期
            std_multiplier: 标准差倍数

        Returns:
            float: 布林带宽度（百分比）
        """
        recent_closes = closes[-period:]

        # 计算中轨（简单移动平均）
        sma = sum(recent_closes) / len(recent_closes)
        if sma == 0:
            return 0.0

        # 计算标准差
        variance = sum((c - sma) ** 2 for c in recent_closes) / len(recent_closes)
        std_dev = math.sqrt(variance)

        # 上轨和下轨
        upper_band = sma + std_multiplier * std_dev
        lower_band = sma - std_multiplier * std_dev

        # 宽度百分比
        bb_width_pct = (upper_band - lower_band) / sma * 100
        return bb_width_pct

    @classmethod
    def _calculate_historical_volatility(
        cls,
        closes: List[float],
        period: int,
    ) -> float:
        """
        计算历史波动率（年化）。

        步骤：
        1. 计算对数收益率序列 ln(P_t / P_{t-1})
        2. 求收益率的标准差
        3. 年化（假设365天交易日，加密货币全年无休）

        Args:
            closes: 收盘价序列
            period: 回看周期

        Returns:
            float: 年化历史波动率（百分比）
        """
        recent_closes = closes[-(period + 1):]
        log_returns: List[float] = []

        for i in range(1, len(recent_closes)):
            if recent_closes[i - 1] > 0 and recent_closes[i] > 0:
                log_return = math.log(recent_closes[i] / recent_closes[i - 1])
                log_returns.append(log_return)

        if len(log_returns) < 2:
            return 0.0

        # 计算对数收益率的均值和标准差
        mean_return = sum(log_returns) / len(log_returns)
        variance = sum((r - mean_return) ** 2 for r in log_returns) / (len(log_returns) - 1)
        std_dev = math.sqrt(variance)

        # 年化：加密货币市场365天运行
        annualized_volatility = std_dev * math.sqrt(365) * 100
        return annualized_volatility

    @classmethod
    def _compute_volatility_score(
        cls,
        atr: float,
        bb_width: float,
        historical_volatility: float,
        current_price: float,
    ) -> float:
        """
        将多维波动率指标合成为0-100评分。

        评分逻辑：
        - ATR 相对值（ATR/价格百分比）贡献 40% 权重
        - 布林带宽度贡献 30% 权重
        - 历史波动率贡献 30% 权重
        各指标通过 sigmoid 映射到 0-100 区间

        Args:
            atr:                  平均真实波幅
            bb_width:             布林带宽度（百分比）
            historical_volatility: 历史波动率（年化百分比）
            current_price:        当前价格

        Returns:
            float: 波动率综合评分（0-100）
        """
        # ATR 转换为相对波动率（百分比），避免除零
        atr_pct = (atr / current_price * 100) if current_price > 0 else 0.0

        # sigmoid 映射：中心点和斜率根据加密市场经验设定
        # ATR%：通常在 0.5%~5% 之间，中心设为 2%
        atr_score = 100.0 / (1.0 + math.exp(-1.5 * (atr_pct - 2.0)))

        # 布林带宽度：通常在 1%~15%，中心设为 5%
        bb_score = 100.0 / (1.0 + math.exp(-0.5 * (bb_width - 5.0)))

        # 历史波动率：年化通常在 20%~200%，中心设为 80%
        hv_score = 100.0 / (1.0 + math.exp(-0.05 * (historical_volatility - 80.0)))

        # 加权合成
        final_score = atr_score * 0.40 + bb_score * 0.30 + hv_score * 0.30

        return max(0.0, min(100.0, final_score))

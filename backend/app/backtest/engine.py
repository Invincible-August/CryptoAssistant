"""
回测引擎核心模块。
支持K线级回测，集成指标和因子计算，输出完整绩效报告。
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd
from loguru import logger
from app.backtest.simulator import TradeSimulator
from app.backtest.metrics import calculate_metrics
from app.modules.feature_pipeline import FeaturePipeline


class BacktestEngine:
    """
    K线级回测引擎。

    工作流程：
    1. 加载历史K线数据
    2. 逐根K线推进
    3. 每根K线上计算指标和因子
    4. 根据策略逻辑生成交易信号
    5. 模拟执行交易
    6. 统计绩效指标
    """

    def __init__(
        self,
        initial_capital: float = 10000.0,
        fee_rate: float = 0.001,
        slippage: float = 0.0005,
    ):
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.feature_pipeline = FeaturePipeline()
        self.simulator = TradeSimulator(initial_capital, fee_rate, slippage)

    async def run(
        self,
        kline_df: pd.DataFrame,
        strategy_config: Dict[str, Any],
        indicator_keys: List[str] = None,
        factor_keys: List[str] = None,
    ) -> Dict[str, Any]:
        """
        运行回测。

        Args:
            kline_df: 历史K线DataFrame，必须包含 open_time, open, high, low, close, volume
            strategy_config: 策略配置
            indicator_keys: 使用的指标列表
            factor_keys: 使用的因子列表

        Returns:
            回测结果字典
        """
        indicator_keys = indicator_keys or ["ema", "rsi", "macd"]
        factor_keys = factor_keys or ["momentum", "volatility"]

        self.feature_pipeline.set_enabled_indicators(indicator_keys)
        self.feature_pipeline.set_enabled_factors(factor_keys)

        warmup_period = strategy_config.get("warmup_period", 60)

        logger.info(
            f"回测开始: 共{len(kline_df)}根K线, 预热期{warmup_period}根, "
            f"初始资金{self.initial_capital}"
        )

        trades: List[Dict[str, Any]] = []
        equity_curve: List[Dict[str, Any]] = []

        for i in range(warmup_period, len(kline_df)):
            # 截取到当前K线的窗口数据
            window_df = kline_df.iloc[max(0, i - 200) : i + 1].copy()
            current_bar = kline_df.iloc[i]
            current_price = float(current_bar["close"])
            current_time = current_bar["open_time"]

            try:
                # 运行特征管线
                features = await self.feature_pipeline.run_full_pipeline(window_df)

                # 从因子结果提取评分
                scores = self._extract_scores(features.get("factor_results", {}))

                # 基于评分和指标生成信号
                signal = self._generate_signal(
                    features, scores, current_price, strategy_config
                )

                # 处理信号
                if signal:
                    trade = self.simulator.process_signal(
                        signal, current_price, current_time
                    )
                    if trade:
                        trades.append(trade)

                # 检查止盈止损
                closed = self.simulator.check_exits(current_price, current_time)
                trades.extend(closed)

            except Exception as e:
                logger.debug(f"回测第{i}根K线处理异常: {e}")

            # 记录净值
            equity = self.simulator.get_equity(current_price)
            equity_curve.append(
                {"time": str(current_time), "equity": equity, "price": current_price}
            )

        # 平掉剩余持仓
        if len(kline_df) > 0:
            final_price = float(kline_df.iloc[-1]["close"])
            final_time = kline_df.iloc[-1]["open_time"]
            remaining = self.simulator.close_all(final_price, final_time)
            trades.extend(remaining)

        # 计算绩效指标
        metrics = calculate_metrics(trades, self.initial_capital, equity_curve)

        logger.info(
            f"回测完成: 总交易{len(trades)}笔, "
            f"总收益率{metrics.get('total_return', 0):.2%}, "
            f"最大回撤{metrics.get('max_drawdown', 0):.2%}"
        )

        return {
            "metrics": metrics,
            "trades": trades,
            "equity_curve": equity_curve,
        }

    def _extract_scores(self, factor_results: Dict) -> Dict[str, float]:
        """从因子结果中提取评分"""
        scores = {}
        for key, result in factor_results.items():
            if isinstance(result, dict) and "score" in result:
                scores[key] = result["score"]
        return scores

    def _generate_signal(
        self,
        features: Dict,
        scores: Dict,
        current_price: float,
        config: Dict,
    ) -> Optional[Dict]:
        """
        根据特征生成交易信号。

        MVP版本策略逻辑：
        - 动量因子 > entry_threshold 且 RSI < 70 → 做多
        - 动量因子 < exit_threshold 且 RSI > 30 → 做空
        - 波动率过高时不交易
        """
        momentum_score = scores.get("momentum", 50)
        volatility_score = scores.get("volatility", 50)

        # 从指标结果中获取RSI
        rsi_value = 50.0
        indicator_results = features.get("indicator_results", {})
        if "rsi" in indicator_results:
            rsi_df = indicator_results["rsi"]
            if not rsi_df.empty and "rsi" in rsi_df.columns:
                last_rsi = rsi_df.iloc[-1].get("rsi")
                if pd.notna(last_rsi):
                    rsi_value = float(last_rsi)

        # 极端波动率时不交易
        if volatility_score > 85:
            return None

        position = self.simulator.get_current_position()

        entry_threshold = config.get("entry_threshold", 65)
        exit_threshold = config.get("exit_threshold", 35)
        position_size = config.get("position_size", 0.1)
        stop_loss_pct = config.get("stop_loss_pct", 0.02)
        take_profit_pct = config.get("take_profit_pct", 0.04)

        # 无持仓时根据信号开仓
        if position is None:
            if momentum_score > entry_threshold and rsi_value < 70:
                return {
                    "direction": "long",
                    "size_ratio": position_size,
                    "stop_loss": current_price * (1 - stop_loss_pct),
                    "take_profit": current_price * (1 + take_profit_pct),
                    "reason": f"动量={momentum_score:.1f}, RSI={rsi_value:.1f}, 做多",
                }
            elif momentum_score < exit_threshold and rsi_value > 30:
                return {
                    "direction": "short",
                    "size_ratio": position_size,
                    "stop_loss": current_price * (1 + stop_loss_pct),
                    "take_profit": current_price * (1 - take_profit_pct),
                    "reason": f"动量={momentum_score:.1f}, RSI={rsi_value:.1f}, 做空",
                }

        return None

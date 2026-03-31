"""
特征管线模块。

负责将原始市场数据转换为指标结果和因子结果，构建完整的分析上下文。

工作流程：
1. 接收原始行情数据（K线、成交、深度等）
2. 批量计算所有已启用的技术指标
3. 将指标结果注入上下文，构建因子计算所需的完整数据环境
4. 批量计算所有已启用的因子
5. 输出完整的特征集合，供评分引擎、假设引擎和AI模块使用

设计理念：
- 管线化处理：指标 -> 上下文构建 -> 因子，层层递进
- 容错机制：单个指标/因子计算失败不影响整条管线
- 可配置性：通过 set_enabled_xxx 灵活控制计算范围
"""
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from app.indicators.registry import indicator_registry
from app.factors.registry import FactorRegistry as factor_registry
from app.services.plugin_runtime_service import get_plugin_runtime_service


class FeaturePipeline:
    """
    特征管线。

    核心职责是将原始行情数据经过多层计算，转化为结构化的特征集合。
    管线的输出将直接供评分引擎（ScoringEngine）和假设引擎（HypothesisEngine）消费。

    工作流程：
    1. 接收原始行情数据（K线DataFrame、附加上下文等）
    2. 遍历已启用的指标列表，逐个调用指标的 calculate 方法
    3. 将K线数据和指标计算结果合并为因子上下文
    4. 遍历已启用的因子列表，逐个调用因子的 calculate + normalize 方法
    5. 返回包含所有指标结果和因子结果的完整特征字典

    Attributes:
        _enabled_indicators: 已启用的指标 key 列表
        _enabled_factors:    已启用的因子 key 列表
    """

    def __init__(self) -> None:
        """初始化空的已启用指标和因子列表。"""
        self._enabled_indicators: List[str] = []
        self._enabled_factors: List[str] = []

    def set_enabled_indicators(self, keys: List[str]) -> None:
        """
        设置本次管线运行需要计算的指标列表。

        Args:
            keys: 指标 key 列表，如 ["ma", "rsi", "volume_spike"]
        """
        self._enabled_indicators = keys
        logger.info(f"特征管线已设置 {len(keys)} 个启用指标: {keys}")

    def set_enabled_factors(self, keys: List[str]) -> None:
        """
        设置本次管线运行需要计算的因子列表。

        Args:
            keys: 因子 key 列表，如 ["momentum", "volume_flow"]
        """
        self._enabled_factors = keys
        logger.info(f"特征管线已设置 {len(keys)} 个启用因子: {keys}")

    async def compute_indicators(
        self,
        kline_df: pd.DataFrame,
        params_map: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        批量计算所有已启用的技术指标。

        对 _enabled_indicators 中的每个指标 key：
        1. 从 indicator_registry 获取对应的指标类
        2. 从 params_map 获取该指标的自定义参数（如无则使用默认参数）
        3. 调用指标类的 calculate 方法执行计算
        4. 将结果 DataFrame 存入结果字典

        单个指标计算失败不会中断整个批量计算流程。

        Args:
            kline_df:   K线数据 DataFrame，至少包含 open, high, low, close, volume 列
            params_map: 可选的指标参数覆盖字典，格式为 {indicator_key: {param_name: value}}

        Returns:
            Dict[str, pd.DataFrame]: {指标key: 计算结果DataFrame} 的映射
        """
        indicator_results: Dict[str, pd.DataFrame] = {}
        params_map = params_map or {}
        runtime = get_plugin_runtime_service()

        for indicator_key in self._enabled_indicators:
            if not runtime.is_indicator_load_enabled(indicator_key):
                logger.debug(
                    f"指标 {indicator_key} 在 plugin_runtime 中禁用，跳过管线计算"
                )
                continue
            try:
                # 从注册中心获取指标类（未注册则抛 KeyError）
                indicator_cls = indicator_registry.get(indicator_key)

                # 获取该指标的自定义参数，无自定义则使用空字典（触发默认值）
                custom_params = params_map.get(indicator_key, {})

                # 调用指标计算方法
                result_df = indicator_cls.calculate(kline_df, custom_params)
                indicator_results[indicator_key] = result_df

                logger.debug(
                    f"指标计算完成: {indicator_key}, "
                    f"结果行数={len(result_df)}"
                )
            except KeyError:
                logger.error(f"指标 {indicator_key} 未注册，跳过计算")
            except Exception as calc_error:
                logger.error(
                    f"指标计算失败 {indicator_key}: {calc_error}",
                    exc_info=True,
                )

        logger.info(
            f"指标批量计算完成: 成功 {len(indicator_results)}/{len(self._enabled_indicators)}"
        )
        return indicator_results

    async def compute_factors(
        self,
        context: Dict[str, Any],
        params_map: Optional[Dict[str, Dict]] = None,
    ) -> Dict[str, Dict]:
        """
        批量计算所有已启用的因子。

        对 _enabled_factors 中的每个因子 key：
        1. 从 factor_registry 获取因子类
        2. 调用因子的 calculate 方法计算原始结果
        3. 调用因子的 normalize 方法将结果归一化
        4. 存入结果字典

        Args:
            context:    因子计算上下文，通常包含 kline DataFrame 和已计算的指标结果
            params_map: 可选的因子参数覆盖字典，格式为 {factor_key: {param_name: value}}

        Returns:
            Dict[str, Dict]: {因子key: 归一化后的因子结果字典} 的映射
        """
        factor_results: Dict[str, Dict] = {}
        params_map = params_map or {}
        runtime = get_plugin_runtime_service()

        for factor_key in self._enabled_factors:
            if not runtime.is_factor_load_enabled(factor_key):
                logger.debug(
                    f"因子 {factor_key} 在 plugin_runtime 中禁用，跳过管线计算"
                )
                continue
            try:
                # 从注册中心获取因子类
                factor_cls = factor_registry.get(factor_key)
                if factor_cls is None:
                    logger.error(f"因子 {factor_key} 未注册，跳过计算")
                    continue

                # 获取因子自定义参数
                custom_params = params_map.get(factor_key, {})

                # 执行因子计算（产出原始结果）
                raw_result = factor_cls.calculate(context, custom_params)

                # 归一化处理（统一评分尺度、字段格式等）
                normalized_result = factor_cls.normalize(raw_result)

                factor_results[factor_key] = normalized_result

                logger.debug(f"因子计算完成: {factor_key}")
            except Exception as calc_error:
                logger.error(
                    f"因子计算失败 {factor_key}: {calc_error}",
                    exc_info=True,
                )

        logger.info(
            f"因子批量计算完成: 成功 {len(factor_results)}/{len(self._enabled_factors)}"
        )
        return factor_results

    async def run_full_pipeline(
        self,
        kline_df: pd.DataFrame,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        运行完整特征管线：指标计算 -> 上下文构建 -> 因子计算。

        这是管线的主入口方法，按以下步骤顺序执行：

        第一步：批量计算技术指标
            以K线数据为输入，计算 RSI、MA、MACD 等所有已启用指标

        第二步：构建因子上下文
            将原始K线数据、指标计算结果和额外上下文（如深度数据、持仓数据等）
            合并为一个完整的因子上下文字典

        第三步：批量计算因子
            以上下文为输入，计算动量因子、资金流因子、波动率因子等

        Args:
            kline_df:      K线数据 DataFrame
            extra_context: 额外上下文数据（如 orderbook、open_interest、funding_rate 等）

        Returns:
            Dict[str, Any]: 完整特征集合，包含：
                - "indicator_results": {指标key: DataFrame} 指标计算结果
                - "factor_results":    {因子key: Dict} 因子计算结果（归一化后）
        """
        extra_context = extra_context or {}

        logger.info("========== 特征管线开始运行 ==========")

        # 第一步：计算技术指标
        indicator_results = await self.compute_indicators(kline_df)

        # 第二步：构建因子上下文
        # 将K线数据和所有指标结果整合到一个上下文字典中，
        # 这样每个因子都可以访问到它所需的任意数据源
        factor_context: Dict[str, Any] = {
            "kline": kline_df,
            "indicators": {k: v for k, v in indicator_results.items()},
            **extra_context,
        }

        # 第三步：计算因子
        factor_results = await self.compute_factors(factor_context)

        logger.info(
            f"========== 特征管线运行完成: "
            f"{len(indicator_results)} 个指标 + {len(factor_results)} 个因子 =========="
        )

        return {
            "indicator_results": indicator_results,
            "factor_results": factor_results,
        }

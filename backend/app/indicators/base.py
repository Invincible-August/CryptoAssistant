"""
指标插件基类模块。
所有技术指标（系统内置、人工自定义、AI生成）都必须继承此基类。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import pandas as pd


class BaseIndicator(ABC):
    """
    指标插件基类。

    所有自定义指标、系统内置指标、AI生成后通过审核的指标，
    都必须继承该基类，并实现统一接口。

    这样可以保证：
    1. 后端可以统一加载和调用指标
    2. 前端可以统一展示指标元数据
    3. 回测模块可以统一读取指标结果
    4. AI模块可以统一识别指标定义

    Attributes:
        indicator_key: 指标的唯一标识符，用于注册和检索
        name: 指标的显示名称
        description: 指标的详细描述
        source: 指标来源，可选 system / human / ai
        version: 指标版本号，遵循语义化版本
        category: 指标分类（trend / momentum / volume / volatility / custom）
        input_type: 指标所需的输入数据类型列表
        chart_compatible: 是否支持图表展示
        backtest_compatible: 是否支持回测
        ai_compatible: 是否支持AI分析
        params_schema: 参数定义schema，描述每个参数的类型、默认值、是否必填
        output_schema: 输出字段定义schema，描述输出DataFrame的列信息
        display_config: 前端图表展示配置，包含面板类型、系列样式等
    """

    # ========== 指标身份标识 ==========
    indicator_key: str = ""       # 唯一标识，如 "ma", "rsi", "volume_spike"
    name: str = ""                # 展示名称，如 "简单移动平均线"
    description: str = ""         # 指标功能说明
    source: str = "system"        # 来源类型：system（系统内置）/ human（人工定义）/ ai（AI生成）
    version: str = "1.0.0"        # 语义化版本号
    category: str = "custom"      # 分类：trend / momentum / volume / volatility / custom

    # ========== 兼容性声明 ==========
    input_type: List[str] = ["kline"]       # 输入数据类型，默认为K线数据
    chart_compatible: bool = True            # 是否兼容前端图表渲染
    backtest_compatible: bool = True         # 是否兼容回测引擎
    ai_compatible: bool = True               # 是否兼容AI信号分析模块

    # ========== Schema 定义 ==========
    params_schema: Dict[str, Any] = {}       # 参数schema，定义指标入参的类型和约束
    output_schema: Dict[str, Any] = {}       # 输出schema，定义计算结果DataFrame的列
    display_config: Dict[str, Any] = {}      # 前端图表渲染配置

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """
        返回指标元数据，供前端展示、数据库注册、插件扫描使用。

        Returns:
            Dict[str, Any]: 包含指标全部元信息的字典，键名与类属性一一对应。
        """
        return {
            "indicator_key": cls.indicator_key,
            "name": cls.name,
            "description": cls.description,
            "source": cls.source,
            "version": cls.version,
            "category": cls.category,
            "input_type": cls.input_type,
            "chart_compatible": cls.chart_compatible,
            "backtest_compatible": cls.backtest_compatible,
            "ai_compatible": cls.ai_compatible,
            "params_schema": cls.params_schema,
            "output_schema": cls.output_schema,
            "display_config": cls.display_config,
        }

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验并补全参数，不合法则抛出 ValueError。

        根据 params_schema 逐项校验用户传入的参数：
        - 缺失的必填参数 → 抛出异常
        - 缺失的可选参数 → 自动填充默认值
        - 类型不匹配 → 抛出异常

        Args:
            params: 用户传入的参数字典。

        Returns:
            Dict[str, Any]: 校验通过并补全默认值后的参数字典。

        Raises:
            ValueError: 当参数缺失或类型不匹配时抛出。
        """
        validated: Dict[str, Any] = {}

        for key, schema in cls.params_schema.items():
            default = schema.get("default")
            required = schema.get("required", False)
            expected_type = schema.get("type")

            # --- 参数缺失时的处理 ---
            if key not in params:
                # 必填参数且无默认值 → 报错
                if required and default is None:
                    raise ValueError(f"缺少必填参数: {key}")
                # 可选参数或有默认值 → 使用默认值
                validated[key] = default
                continue

            value = params[key]

            # --- 类型校验：逐一检查支持的类型 ---
            if expected_type == "int" and not isinstance(value, int):
                raise ValueError(f"参数 {key} 必须是 int 类型")
            if expected_type == "float" and not isinstance(value, (int, float)):
                raise ValueError(f"参数 {key} 必须是 float 类型")
            if expected_type == "str" and not isinstance(value, str):
                raise ValueError(f"参数 {key} 必须是 str 类型")
            if expected_type == "bool" and not isinstance(value, bool):
                raise ValueError(f"参数 {key} 必须是 bool 类型")

            validated[key] = value

        return validated

    @classmethod
    @abstractmethod
    def calculate(cls, df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """
        核心计算方法，子类必须实现。

        接收原始K线数据和参数，返回包含指标计算结果的DataFrame。
        子类实现时应先调用 validate_params() 校验参数。

        Args:
            df: 包含K线数据的DataFrame，至少包含 open_time, close, volume 等列。
            params: 指标参数字典，具体内容由 params_schema 定义。

        Returns:
            pd.DataFrame: 包含计算结果的DataFrame，列名由 output_schema 定义。

        Raises:
            NotImplementedError: 子类未实现该方法时抛出。
        """
        raise NotImplementedError

    @classmethod
    def format_for_chart(cls, result_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        将指标结果转换为前端图表可直接消费的格式。

        遍历结果DataFrame的每一行，以 open_time 作为时间轴，
        其余字段作为数据系列，生成前端TradingView等图表库可用的数据列表。

        Args:
            result_df: calculate() 方法返回的指标结果DataFrame。

        Returns:
            List[Dict[str, Any]]: 前端图表数据列表，每项包含 time 和各指标字段。
        """
        records: List[Dict[str, Any]] = []
        for _, row in result_df.iterrows():
            # 每行以 open_time 为时间基准，附带所有指标字段
            item: Dict[str, Any] = {"time": row["open_time"]}
            for col in result_df.columns:
                if col != "open_time":
                    item[col] = row[col]
            records.append(item)
        return records

    @classmethod
    def format_for_signal(cls, result_df: pd.DataFrame) -> Dict[str, Any]:
        """
        将指标结果转换为信号分析模块的格式。

        提取最新一条数据和最近20条历史数据，
        供AI信号分析模块和策略引擎使用。

        Args:
            result_df: calculate() 方法返回的指标结果DataFrame。

        Returns:
            Dict[str, Any]: 包含 latest（最新值字典）和 series（最近20条记录列表）。
        """
        if result_df.empty:
            return {"latest": None, "series": []}

        # 取最新一条记录作为当前状态
        latest: Dict[str, Any] = result_df.iloc[-1].to_dict()
        # 取最近20条作为短期历史序列
        recent: List[Dict[str, Any]] = result_df.tail(20).to_dict(orient="records")

        return {"latest": latest, "series": recent}

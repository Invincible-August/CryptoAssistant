"""
技术指标相关数据模型

定义指标元数据、计算请求和计算结果等结构，
支持动态指标注册和前端图表渲染。
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class IndicatorMeta(BaseModel):
    """
    技术指标元信息模型

    描述一个指标的完整元数据，包括参数 schema、输出格式和兼容性标记。
    由指标注册中心统一管理，前端据此动态渲染指标配置面板。

    Attributes:
        indicator_key: 指标唯一标识（如 rsi, macd, bollinger）
        name: 指标显示名称
        description: 指标功能描述
        source: 来源模块或作者
        version: 指标版本号
        category: 指标分类（trend / momentum / volatility / volume）
        params_schema: 参数 JSON Schema，定义可调参数
        output_schema: 输出 JSON Schema，描述返回数据结构
        display_config: 前端展示配置（颜色、线型等）
        chart_compatible: 是否支持图表渲染
        backtest_compatible: 是否支持回测引用
        ai_compatible: 是否支持 AI 分析引用
    """

    model_config = ConfigDict(from_attributes=True)

    indicator_key: str = Field(..., description="指标唯一标识")
    name: str = Field(..., description="指标显示名称")
    description: str = Field(default="", description="指标功能描述")
    source: str = Field(default="system", description="来源模块或作者")
    version: str = Field(default="1.0.0", description="版本号")
    category: str = Field(
        default="custom",
        description="分类：trend / momentum / volatility / volume / custom",
    )
    params_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="参数 JSON Schema",
    )
    output_schema: Dict[str, Any] = Field(
        default_factory=dict,
        description="输出 JSON Schema",
    )
    display_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="前端展示配置（颜色、线型等）",
    )
    chart_compatible: bool = Field(default=True, description="是否支持图表渲染")
    backtest_compatible: bool = Field(default=True, description="是否支持回测")
    ai_compatible: bool = Field(default=False, description="是否支持 AI 分析引用")


class IndicatorPluginLoadRequest(BaseModel):
    """
    Request body to enable or disable an indicator in plugin_runtime.yaml.
    """

    indicator_key: str = Field(..., min_length=1, description="Registered indicator_key")
    load_enabled: bool = Field(
        ...,
        description="False = skip in calculate / pipelines",
    )


class IndicatorCalcRequest(BaseModel):
    """
    指标计算请求模型

    前端或策略引擎请求计算某个指标时提交的参数。

    Attributes:
        indicator_key: 要计算的指标标识
        symbol: 交易对
        exchange: 交易所名称
        market_type: 市场类型
        timeframe: 时间周期（如 1m, 5m, 1h）
        params: 指标计算参数，覆盖默认值
    """

    indicator_key: str = Field(..., description="指标标识")
    symbol: str = Field(..., description="交易对")
    exchange: str = Field(default="binance", description="交易所名称")
    market_type: str = Field(default="spot", description="市场类型")
    timeframe: str = Field(default="1h", description="时间周期")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="计算参数，如 {\"period\": 14}",
    )


class IndicatorCalcResponse(BaseModel):
    """
    指标计算结果响应模型

    返回计算完成的指标数据，包含序列定义和时间序列数据点。

    Attributes:
        indicator_key: 指标标识
        name: 指标显示名称
        source: 计算来源
        panel: 显示面板（main 主图 / sub 副图）
        series: 数据系列定义列表（名称、颜色、类型等）
        data: 时间序列数据点列表
    """

    indicator_key: str = Field(..., description="指标标识")
    name: str = Field(..., description="指标名称")
    source: str = Field(default="system", description="计算来源")
    panel: str = Field(
        default="sub",
        description="显示面板：main（主图叠加）/ sub（副图独立）",
    )
    series: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="序列定义，如 [{\"name\": \"RSI\", \"color\": \"#FF6600\"}]",
    )
    data: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="时间序列数据点",
    )

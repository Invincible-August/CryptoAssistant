"""
因子插件基类模块。
所有因子（系统内置、人工自定义、AI生成）都必须继承此基类。
因子与指标的区别：因子更偏向策略分析和特征提取，
可以依赖多种数据源（K线、成交、深度、OI、资金费率等）。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseFactor(ABC):
    """
    因子插件基类。

    因子主要服务于：
    1. 行为分析 —— 解读市场参与者行为模式
    2. 信号评分 —— 输出标准化的0-100评分供信号合成使用
    3. AI输入   —— 作为AI模型的结构化特征向量
    4. 回测逻辑 —— 在历史数据上可复现的计算流程
    5. 主导资金画像推断 —— 结合多因子综合判断主力行为

    Attributes:
        factor_key:          因子唯一标识符（英文蛇形命名，全局不可重复）
        name:                因子显示名称（中文友好名）
        description:         因子描述（说明计算逻辑和适用场景）
        source:              因子来源：system（内置）/ human（人工）/ ai（AI生成）
        version:             语义化版本号
        category:            因子类别（momentum / volatility / flow / microstructure / positioning / custom）
        input_type:          依赖的数据源列表（kline / orderbook / open_interest / funding_rate / trades）
        score_weight:        评分权重（在多因子合成时使用）
        signal_compatible:   是否兼容信号分析模块
        backtest_compatible: 是否兼容回测模块
        ai_compatible:       是否兼容AI特征输入模块
        params_schema:       参数定义（JSON Schema 风格）
        output_schema:       输出字段定义
        display_config:      前端图表展示配置
    """

    # ==================== 因子基本属性 ====================
    factor_key: str = ""          # 因子唯一标识，例如 "momentum"
    name: str = ""                # 因子中文名称
    description: str = ""         # 因子功能描述
    source: str = "system"        # 来源：system / human / ai
    version: str = "1.0.0"        # 语义化版本号
    category: str = "custom"      # 因子分类
    input_type: List[str] = []    # 依赖的数据源类型

    # ==================== 因子能力声明 ====================
    score_weight: float = 1.0             # 评分合成权重
    signal_compatible: bool = True        # 信号模块兼容性
    backtest_compatible: bool = True      # 回测模块兼容性
    ai_compatible: bool = True            # AI特征兼容性

    # ==================== 因子Schema定义 ====================
    params_schema: Dict[str, Any] = {}    # 输入参数定义（含类型、默认值、必填性）
    output_schema: Dict[str, Any] = {}    # 输出字段定义（含类型和描述）
    display_config: Dict[str, Any] = {}   # 前端图表展示配置

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """
        返回因子元数据字典。

        元数据包含因子的所有静态属性，供注册中心索引、前端展示
        以及AI模型识别因子能力时使用。

        Returns:
            Dict[str, Any]: 因子完整元数据
        """
        return {
            "factor_key": cls.factor_key,
            "name": cls.name,
            "description": cls.description,
            "source": cls.source,
            "version": cls.version,
            "category": cls.category,
            "input_type": cls.input_type,
            "score_weight": cls.score_weight,
            "signal_compatible": cls.signal_compatible,
            "backtest_compatible": cls.backtest_compatible,
            "ai_compatible": cls.ai_compatible,
            "params_schema": cls.params_schema,
            "output_schema": cls.output_schema,
            "display_config": cls.display_config,
        }

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        校验并补全因子参数。

        根据 params_schema 定义逐一检查传入参数：
        - 缺失的必填参数抛出 ValueError
        - 缺失的可选参数填充默认值
        - 类型不匹配的参数抛出 ValueError

        Args:
            params: 用户传入的参数字典

        Returns:
            Dict[str, Any]: 校验通过并补全默认值后的参数字典

        Raises:
            ValueError: 当必填参数缺失或参数类型不匹配时
        """
        validated: Dict[str, Any] = {}

        for key, schema in cls.params_schema.items():
            default = schema.get("default")
            required = schema.get("required", False)
            expected_type = schema.get("type")

            # 参数缺失时：必填参数无默认值则报错，否则填充默认值
            if key not in params:
                if required and default is None:
                    raise ValueError(f"缺少必填参数: {key}")
                validated[key] = default
                continue

            value = params[key]

            # 按照声明的类型进行严格校验
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
    def calculate(cls, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算因子结果，子类必须实现此方法。

        这是因子的核心计算入口。每个因子子类需根据自身逻辑，
        从 context 中提取所需数据源，结合 params 完成计算。

        Args:
            context: 数据上下文，包含 kline、orderbook、open_interest 等数据
            params:  经过 validate_params 校验后的参数字典

        Returns:
            Dict[str, Any]: 计算结果字典，结构需符合 output_schema 定义

        Raises:
            NotImplementedError: 子类未实现此方法时抛出
        """
        raise NotImplementedError

    @classmethod
    def normalize(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        将因子计算结果归一化到统一结构。

        默认直接返回原始结果，子类可覆写此方法以添加
        标准化评分、统一字段名称等后处理逻辑。

        Args:
            result: calculate() 返回的原始计算结果

        Returns:
            Dict[str, Any]: 归一化后的结果字典
        """
        return result

    @classmethod
    def format_for_signal(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换为信号分析模块可用格式。

        信号模块需要标准化的 factor_key + score + direction 结构，
        子类可覆写此方法以自定义转换逻辑。

        Args:
            result: 计算或归一化后的结果字典

        Returns:
            Dict[str, Any]: 信号模块可消费的格式
        """
        return result

    @classmethod
    def format_for_chart(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换为前端图表可展示格式。

        根据 display_config 定义的图表类型（折线图、柱状图、热力图等），
        将数据转换为前端组件所需的数据结构。

        Args:
            result: 计算或归一化后的结果字典

        Returns:
            Dict[str, Any]: 前端图表组件可渲染的数据格式
        """
        return result

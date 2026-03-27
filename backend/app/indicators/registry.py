"""
指标注册中心模块。
支持手动注册、自动扫描注册、按来源过滤。
所有指标插件在系统启动时统一注册到此中心，供后续调用。
"""
import importlib
import pkgutil
from typing import Dict, List, Optional, Type

from loguru import logger

from app.indicators.base import BaseIndicator


class IndicatorRegistry:
    """
    指标注册中心，统一管理所有指标插件。

    通过单例模式在全局维护一份指标注册表，提供：
    - 手动注册指标类
    - 按 indicator_key 检索指标
    - 按来源（system/human/ai）过滤指标
    - 自动扫描包路径并注册所有发现的指标

    Attributes:
        _indicators: 内部指标注册字典，key为指标唯一标识，value为指标类。
    """

    def __init__(self) -> None:
        """初始化空的指标注册表。"""
        self._indicators: Dict[str, Type[BaseIndicator]] = {}

    def register(self, indicator_cls: Type[BaseIndicator]) -> None:
        """
        注册一个指标类到注册中心。

        Args:
            indicator_cls: 继承自 BaseIndicator 的指标类。

        Raises:
            ValueError: 当指标类缺少 indicator_key 时抛出。
        """
        key: str = indicator_cls.indicator_key
        if not key:
            raise ValueError("指标类缺少 indicator_key")
        self._indicators[key] = indicator_cls
        logger.info(f"指标已注册: {key} ({indicator_cls.name})")

    def get(self, indicator_key: str) -> Type[BaseIndicator]:
        """
        根据指标唯一标识获取指标类。

        Args:
            indicator_key: 指标的唯一标识符，如 "ma"、"rsi"。

        Returns:
            Type[BaseIndicator]: 对应的指标类。

        Raises:
            KeyError: 当指标未注册时抛出。
        """
        if indicator_key not in self._indicators:
            raise KeyError(f"未找到指标: {indicator_key}")
        return self._indicators[indicator_key]

    def list_all(self) -> List[Dict]:
        """
        返回全部已注册指标的元数据列表。

        Returns:
            List[Dict]: 每个元素为一个指标的 get_metadata() 返回值。
        """
        return [ind.get_metadata() for ind in self._indicators.values()]

    def list_by_source(self, source: str) -> List[Dict]:
        """
        按来源筛选已注册指标。

        Args:
            source: 指标来源，可选 "system" / "human" / "ai"。

        Returns:
            List[Dict]: 符合来源条件的指标元数据列表。
        """
        return [
            ind.get_metadata()
            for ind in self._indicators.values()
            if ind.source == source
        ]

    def list_keys(self) -> List[str]:
        """
        返回所有已注册的指标 key 列表。

        Returns:
            List[str]: 已注册指标的 indicator_key 列表。
        """
        return list(self._indicators.keys())

    def auto_discover(self, package_path: str, package_name: str) -> None:
        """
        自动扫描指定包路径下的所有指标模块并注册。

        遍历包内所有模块，查找继承自 BaseIndicator 的类，
        如果该类定义了 indicator_key 则自动注册。

        Args:
            package_path: 包的文件系统路径（用于日志标识）。
            package_name: 包的Python导入路径，如 "app.indicators.builtins"。
        """
        try:
            # 动态导入目标包
            package = importlib.import_module(package_name)
            # 遍历包内的所有子模块
            for importer, module_name, is_pkg in pkgutil.iter_modules(
                package.__path__
            ):
                full_module_name: str = f"{package_name}.{module_name}"
                try:
                    # 动态导入子模块
                    module = importlib.import_module(full_module_name)
                    # 扫描模块中所有属性，查找指标类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        # 条件：是类 + 继承BaseIndicator + 不是基类本身 + 有indicator_key
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, BaseIndicator)
                            and attr is not BaseIndicator
                            and attr.indicator_key
                        ):
                            self.register(attr)
                except Exception as e:
                    logger.error(f"加载指标模块失败 {full_module_name}: {e}")
        except Exception as e:
            logger.error(f"扫描指标包失败 {package_name}: {e}")


# ========== 全局指标注册中心单例 ==========
# 整个应用生命周期内只维护一个注册中心实例
indicator_registry = IndicatorRegistry()

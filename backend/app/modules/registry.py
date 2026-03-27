"""
模块注册中心。
管理所有可插拔模块的启用/禁用状态。

职责：
1. 维护全局模块注册表，记录每个模块的名称、启用状态和实例引用
2. 提供模块的启用/禁用切换接口
3. 支持按名称获取模块实例，实现运行时动态调用
4. 作为系统配置中心，统一管控所有可插拔模块的生命周期
"""
from typing import Dict, Optional

from loguru import logger


class ModuleRegistry:
    """
    系统模块注册中心。

    所有可插拔模块（指标引擎、因子引擎、评分引擎、假设引擎、建议引擎等）
    在系统启动时注册到此中心，运行时通过此中心查询模块状态和获取模块实例。

    Attributes:
        _modules:   模块名称 -> 是否启用的映射表
        _instances:  模块名称 -> 模块实例的映射表
    """

    def __init__(self) -> None:
        """初始化空的模块注册表和实例缓存。"""
        # 模块名 -> 是否启用（True/False）
        self._modules: Dict[str, bool] = {}
        # 模块名 -> 模块实例对象（可选，部分模块可能只注册状态不注册实例）
        self._instances: Dict[str, object] = {}

    def register(
        self,
        module_name: str,
        enabled: bool = False,
        instance: object = None,
    ) -> None:
        """
        注册一个模块到注册中心。

        Args:
            module_name: 模块唯一名称，如 "scoring_engine"、"hypothesis_engine"
            enabled:     初始启用状态，默认关闭
            instance:    模块实例对象，可选；后续可通过 get_instance 获取
        """
        self._modules[module_name] = enabled
        if instance is not None:
            self._instances[module_name] = instance
        logger.info(f"模块已注册: {module_name}, 启用状态: {enabled}")

    def is_enabled(self, module_name: str) -> bool:
        """
        检查指定模块是否处于启用状态。

        Args:
            module_name: 模块名称

        Returns:
            bool: 已启用返回 True，未注册或已禁用返回 False
        """
        return self._modules.get(module_name, False)

    def enable(self, module_name: str) -> None:
        """
        启用指定模块。

        如果模块尚未注册，会自动注册并设为启用状态。

        Args:
            module_name: 要启用的模块名称
        """
        if module_name not in self._modules:
            logger.warning(f"模块 {module_name} 未注册，将自动注册并启用")
        self._modules[module_name] = True
        logger.info(f"模块已启用: {module_name}")

    def disable(self, module_name: str) -> None:
        """
        禁用指定模块。

        Args:
            module_name: 要禁用的模块名称
        """
        if module_name not in self._modules:
            logger.warning(f"模块 {module_name} 未注册，无法禁用")
            return
        self._modules[module_name] = False
        logger.info(f"模块已禁用: {module_name}")

    def get_instance(self, module_name: str) -> Optional[object]:
        """
        获取已注册模块的实例对象。

        Args:
            module_name: 模块名称

        Returns:
            模块实例对象，未注册时返回 None
        """
        if module_name not in self._instances:
            logger.debug(f"模块 {module_name} 未注册实例")
            return None
        return self._instances[module_name]

    def set_instance(self, module_name: str, instance: object) -> None:
        """
        为已注册的模块设置或更新实例对象。

        Args:
            module_name: 模块名称
            instance:    模块实例对象
        """
        self._instances[module_name] = instance
        logger.debug(f"模块实例已更新: {module_name}")

    def unregister(self, module_name: str) -> None:
        """
        从注册中心移除模块（同时清除实例引用）。

        Args:
            module_name: 要移除的模块名称
        """
        self._modules.pop(module_name, None)
        self._instances.pop(module_name, None)
        logger.info(f"模块已注销: {module_name}")

    def list_all(self) -> Dict[str, bool]:
        """
        列出所有已注册模块及其启用状态。

        Returns:
            Dict[str, bool]: {模块名: 是否启用} 的副本
        """
        return self._modules.copy()

    def list_enabled(self) -> list[str]:
        """
        列出所有已启用的模块名称。

        Returns:
            list[str]: 已启用模块名称列表
        """
        return [name for name, enabled in self._modules.items() if enabled]

    def list_disabled(self) -> list[str]:
        """
        列出所有已禁用的模块名称。

        Returns:
            list[str]: 已禁用模块名称列表
        """
        return [name for name, enabled in self._modules.items() if not enabled]

    def count(self) -> int:
        """
        返回已注册模块总数。

        Returns:
            int: 模块总数
        """
        return len(self._modules)


# ========== 全局模块注册中心单例 ==========
# 整个应用生命周期内只维护一个注册中心实例
module_registry = ModuleRegistry()

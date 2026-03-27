"""
因子注册中心模块。
负责自动扫描、注册、管理所有因子插件。
支持按 factor_key 获取、按 category 过滤、列出元数据等操作。
"""
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from loguru import logger

from app.factors.base import BaseFactor


class FactorRegistry:
    """
    因子注册中心（单例模式）。

    职责：
    1. 自动扫描 builtins/ 和 custom/ 目录下的因子模块
    2. 注册所有继承了 BaseFactor 的非抽象子类
    3. 提供按 factor_key 获取、按 category 筛选等查询接口
    4. 防止 factor_key 重复注册

    Attributes:
        _factors: 已注册因子的字典，key 为 factor_key，value 为因子类
    """

    # 存储所有已注册的因子类：{factor_key: FactorClass}
    _factors: Dict[str, Type[BaseFactor]] = {}

    @classmethod
    def register(cls, factor_cls: Type[BaseFactor]) -> None:
        """
        注册单个因子类到注册中心。

        Args:
            factor_cls: 继承自 BaseFactor 的因子类

        Raises:
            ValueError: 当 factor_key 为空或已存在重复注册时
        """
        factor_key = factor_cls.factor_key

        # 校验 factor_key 不能为空
        if not factor_key:
            logger.warning(
                f"因子类 {factor_cls.__name__} 未设置 factor_key，跳过注册"
            )
            return

        # 防止重复注册：相同 factor_key 只允许注册一次
        if factor_key in cls._factors:
            existing_cls = cls._factors[factor_key]
            logger.warning(
                f"因子 factor_key='{factor_key}' 已被 {existing_cls.__name__} 注册，"
                f"跳过 {factor_cls.__name__} 的重复注册"
            )
            return

        cls._factors[factor_key] = factor_cls
        logger.info(
            f"因子注册成功: [{factor_cls.source}] {factor_key} -> {factor_cls.__name__} "
            f"(v{factor_cls.version}, 类别={factor_cls.category})"
        )

    @classmethod
    def get(cls, factor_key: str) -> Optional[Type[BaseFactor]]:
        """
        根据 factor_key 获取已注册的因子类。

        Args:
            factor_key: 因子唯一标识

        Returns:
            对应的因子类，未找到时返回 None
        """
        return cls._factors.get(factor_key)

    @classmethod
    def get_all(cls) -> Dict[str, Type[BaseFactor]]:
        """
        获取所有已注册因子的字典副本。

        Returns:
            Dict[str, Type[BaseFactor]]: {factor_key: FactorClass} 的副本
        """
        return dict(cls._factors)

    @classmethod
    def list_metadata(cls) -> List[Dict[str, Any]]:
        """
        列出所有已注册因子的元数据。

        Returns:
            List[Dict[str, Any]]: 每个因子的 get_metadata() 结果列表
        """
        return [
            factor_cls.get_metadata()
            for factor_cls in cls._factors.values()
        ]

    @classmethod
    def filter_by_category(cls, category: str) -> Dict[str, Type[BaseFactor]]:
        """
        按类别筛选因子。

        Args:
            category: 因子类别名称（如 momentum / volatility / flow 等）

        Returns:
            Dict[str, Type[BaseFactor]]: 匹配该类别的因子字典
        """
        return {
            key: factor_cls
            for key, factor_cls in cls._factors.items()
            if factor_cls.category == category
        }

    @classmethod
    def filter_by_source(cls, source: str) -> Dict[str, Type[BaseFactor]]:
        """
        按来源筛选因子。

        Args:
            source: 因子来源（system / human / ai）

        Returns:
            Dict[str, Type[BaseFactor]]: 匹配该来源的因子字典
        """
        return {
            key: factor_cls
            for key, factor_cls in cls._factors.items()
            if factor_cls.source == source
        }

    @classmethod
    def filter_by_input_type(cls, input_type: str) -> Dict[str, Type[BaseFactor]]:
        """
        按数据源依赖类型筛选因子。

        Args:
            input_type: 数据源类型（kline / orderbook / open_interest / trades 等）

        Returns:
            Dict[str, Type[BaseFactor]]: 输入依赖包含指定类型的因子字典
        """
        return {
            key: factor_cls
            for key, factor_cls in cls._factors.items()
            if input_type in factor_cls.input_type
        }

    @classmethod
    def scan_and_register(cls, package_path: str, package_name: str) -> int:
        """
        自动扫描指定包路径下的所有模块，注册发现的因子类。

        扫描逻辑：
        1. 遍历包路径下所有 .py 模块（递归）
        2. 动态导入每个模块
        3. 检查模块中所有类，找到 BaseFactor 的非抽象子类
        4. 调用 register() 注册找到的因子类

        Args:
            package_path: 包的文件系统路径
            package_name: 包的 Python 导入路径（如 "app.factors.builtins"）

        Returns:
            int: 本次扫描成功注册的因子数量
        """
        registered_count = 0
        package_dir = Path(package_path)

        if not package_dir.exists():
            logger.warning(f"因子包路径不存在: {package_path}")
            return 0

        logger.info(f"开始扫描因子目录: {package_name} ({package_path})")

        # 使用 pkgutil 遍历包下所有子模块
        for importer, module_name, is_pkg in pkgutil.walk_packages(
            path=[str(package_dir)],
            prefix=f"{package_name}.",
        ):
            try:
                # 动态导入模块
                module = importlib.import_module(module_name)
                logger.debug(f"扫描模块: {module_name}")

                # 遍历模块中的所有成员，查找 BaseFactor 子类
                for attr_name, attr_value in inspect.getmembers(module, inspect.isclass):
                    # 必须是 BaseFactor 的子类，且不是 BaseFactor 自身，且不是抽象类
                    if (
                        issubclass(attr_value, BaseFactor)
                        and attr_value is not BaseFactor
                        and not inspect.isabstract(attr_value)
                    ):
                        cls.register(attr_value)
                        registered_count += 1

            except Exception as scan_error:
                logger.error(
                    f"扫描模块 {module_name} 时出错: {scan_error}",
                    exc_info=True,
                )

        logger.info(
            f"因子目录扫描完成: {package_name}，"
            f"本次注册 {registered_count} 个因子"
        )
        return registered_count

    @classmethod
    def clear(cls) -> None:
        """
        清空所有已注册的因子。
        主要用于单元测试时重置注册中心状态。
        """
        cls._factors.clear()
        logger.info("因子注册中心已清空")

    @classmethod
    def count(cls) -> int:
        """
        返回当前已注册因子总数。

        Returns:
            int: 已注册因子数量
        """
        return len(cls._factors)

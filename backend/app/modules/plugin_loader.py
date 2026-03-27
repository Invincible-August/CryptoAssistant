"""
插件发现与加载模块。

职责：
1. 扫描指定目录下的所有 Python 插件文件
2. 动态加载插件模块，从中发现指标类和因子类
3. 将发现的插件自动注册到对应的注册中心（indicator_registry / factor_registry）
4. 支持热加载——运行时动态加入新插件而无需重启系统

设计思路：
- 采用 importlib 动态导入机制，避免硬编码依赖
- 插件文件命名约定：以 .py 结尾、不以 _ 开头（排除 __init__.py 等内部文件）
- 自动识别模块中继承了 BaseIndicator 或 BaseFactor 的非抽象子类
"""
import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from app.indicators.base import BaseIndicator
from app.indicators.registry import indicator_registry
from app.factors.base import BaseFactor
from app.factors.registry import FactorRegistry as factor_registry_cls


def scan_plugins(directory: str) -> List[Path]:
    """
    扫描指定目录下的所有有效插件文件。

    扫描规则：
    - 仅扫描 .py 后缀的文件
    - 排除以下划线 _ 开头的文件（如 __init__.py、_internal.py）
    - 不递归扫描子目录（子目录应使用单独的 scan_plugins 调用）

    Args:
        directory: 要扫描的目录路径（绝对路径或相对路径）

    Returns:
        List[Path]: 发现的插件文件路径列表，按文件名排序
    """
    plugin_dir = Path(directory)

    if not plugin_dir.exists():
        logger.warning(f"插件目录不存在: {directory}")
        return []

    if not plugin_dir.is_dir():
        logger.warning(f"指定路径不是目录: {directory}")
        return []

    # 收集所有合法的插件文件路径
    discovered_plugin_files: List[Path] = []

    for file_path in sorted(plugin_dir.glob("*.py")):
        # 排除以下划线开头的内部文件
        if file_path.name.startswith("_"):
            logger.debug(f"跳过内部文件: {file_path.name}")
            continue

        discovered_plugin_files.append(file_path)
        logger.debug(f"发现插件文件: {file_path.name}")

    logger.info(
        f"插件目录扫描完成: {directory}，发现 {len(discovered_plugin_files)} 个插件文件"
    )
    return discovered_plugin_files


def load_plugin(module_path: str, module_name: Optional[str] = None) -> Optional[Any]:
    """
    动态加载单个插件模块。

    使用 importlib.util 从文件路径动态创建模块规格（spec），
    然后执行模块代码，返回加载完成的模块对象。

    Args:
        module_path: 插件文件的完整路径
        module_name: 可选的模块名，不提供时从文件名自动推断

    Returns:
        加载成功的模块对象，加载失败返回 None
    """
    file_path = Path(module_path)

    if not file_path.exists():
        logger.error(f"插件文件不存在: {module_path}")
        return None

    # 如果未指定模块名，则从文件名（去掉 .py 后缀）推断
    if module_name is None:
        module_name = file_path.stem

    try:
        # 第一步：根据文件路径创建模块规格（包含加载器信息和模块位置）
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            logger.error(f"无法创建模块规格: {module_path}")
            return None

        # 第二步：根据规格创建空模块对象
        module = importlib.util.module_from_spec(spec)

        # 第三步：执行模块代码，填充模块对象的属性
        spec.loader.exec_module(module)

        logger.info(f"插件模块加载成功: {module_name} ({module_path})")
        return module

    except Exception as load_error:
        logger.error(f"加载插件模块失败 {module_path}: {load_error}", exc_info=True)
        return None


def _register_indicators_from_module(module: Any) -> int:
    """
    从已加载的模块中扫描并注册所有指标类。

    扫描逻辑：
    1. 遍历模块中的所有属性
    2. 筛选出继承自 BaseIndicator 的类
    3. 排除 BaseIndicator 自身和抽象类
    4. 要求类必须定义了 indicator_key
    5. 调用 indicator_registry.register() 完成注册

    Args:
        module: 已加载的 Python 模块对象

    Returns:
        int: 本次成功注册的指标数量
    """
    registered_indicator_count = 0

    for attr_name in dir(module):
        attr = getattr(module, attr_name)

        # 条件过滤：必须是类、是 BaseIndicator 子类、不是基类本身、不是抽象类
        if not (
            inspect.isclass(attr)
            and issubclass(attr, BaseIndicator)
            and attr is not BaseIndicator
            and not inspect.isabstract(attr)
        ):
            continue

        # 必须定义了 indicator_key 才能注册
        if not getattr(attr, "indicator_key", ""):
            logger.warning(f"指标类 {attr.__name__} 未定义 indicator_key，跳过")
            continue

        try:
            indicator_registry.register(attr)
            registered_indicator_count += 1
        except Exception as reg_error:
            logger.error(f"注册指标 {attr.__name__} 失败: {reg_error}")

    return registered_indicator_count


def _register_factors_from_module(module: Any) -> int:
    """
    从已加载的模块中扫描并注册所有因子类。

    扫描逻辑与指标类似：
    1. 遍历模块属性
    2. 筛选 BaseFactor 的非抽象子类
    3. 要求定义了 factor_key
    4. 调用 factor_registry.register() 注册

    Args:
        module: 已加载的 Python 模块对象

    Returns:
        int: 本次成功注册的因子数量
    """
    registered_factor_count = 0

    for attr_name in dir(module):
        attr = getattr(module, attr_name)

        # 条件过滤：类 + BaseFactor子类 + 非基类 + 非抽象
        if not (
            inspect.isclass(attr)
            and issubclass(attr, BaseFactor)
            and attr is not BaseFactor
            and not inspect.isabstract(attr)
        ):
            continue

        # 必须定义了 factor_key
        if not getattr(attr, "factor_key", ""):
            logger.warning(f"因子类 {attr.__name__} 未定义 factor_key，跳过")
            continue

        try:
            factor_registry_cls.register(attr)
            registered_factor_count += 1
        except Exception as reg_error:
            logger.error(f"注册因子 {attr.__name__} 失败: {reg_error}")

    return registered_factor_count


def load_and_register_plugins(directory: str) -> Dict[str, int]:
    """
    一键扫描、加载并注册指定目录下的所有插件。

    完整流程：
    1. 调用 scan_plugins() 发现所有插件文件
    2. 逐个调用 load_plugin() 动态加载模块
    3. 对每个加载成功的模块，分别扫描并注册指标类和因子类
    4. 汇总注册结果并返回

    Args:
        directory: 插件目录路径

    Returns:
        Dict[str, int]: 注册结果统计，包含以下键：
            - "scanned_files":        扫描到的插件文件数
            - "loaded_modules":       成功加载的模块数
            - "registered_indicators": 注册的指标数
            - "registered_factors":    注册的因子数
    """
    # 统计结果
    result_summary: Dict[str, int] = {
        "scanned_files": 0,
        "loaded_modules": 0,
        "registered_indicators": 0,
        "registered_factors": 0,
    }

    # 第一步：扫描插件文件
    plugin_files = scan_plugins(directory)
    result_summary["scanned_files"] = len(plugin_files)

    if not plugin_files:
        logger.info(f"目录 {directory} 下未发现插件文件，跳过加载")
        return result_summary

    # 第二步：逐个加载并注册
    for plugin_file_path in plugin_files:
        loaded_module = load_plugin(str(plugin_file_path))

        if loaded_module is None:
            # 加载失败，跳过该文件
            continue

        result_summary["loaded_modules"] += 1

        # 从模块中扫描并注册指标和因子
        indicator_count = _register_indicators_from_module(loaded_module)
        factor_count = _register_factors_from_module(loaded_module)

        result_summary["registered_indicators"] += indicator_count
        result_summary["registered_factors"] += factor_count

    logger.info(
        f"插件加载完成: 扫描 {result_summary['scanned_files']} 个文件, "
        f"加载 {result_summary['loaded_modules']} 个模块, "
        f"注册 {result_summary['registered_indicators']} 个指标 + "
        f"{result_summary['registered_factors']} 个因子"
    )

    return result_summary


def reload_plugin(module_path: str, module_name: Optional[str] = None) -> bool:
    """
    热重载单个插件模块。

    先清除旧的模块缓存，再重新加载并注册。
    适用于开发阶段的快速迭代和运行时插件更新场景。

    注意事项：
    - 热重载不会自动注销旧的指标/因子注册（注册中心的去重机制会拦截重复注册）
    - 如果插件的 indicator_key 或 factor_key 发生变更，旧的注册项需要手动清理

    Args:
        module_path: 插件文件路径
        module_name: 可选的模块名

    Returns:
        bool: 重载是否成功
    """
    loaded_module = load_plugin(module_path, module_name)

    if loaded_module is None:
        return False

    # 重新注册模块中的指标和因子
    indicator_count = _register_indicators_from_module(loaded_module)
    factor_count = _register_factors_from_module(loaded_module)

    logger.info(
        f"插件热重载完成: {module_path}, "
        f"注册 {indicator_count} 个指标 + {factor_count} 个因子"
    )
    return True

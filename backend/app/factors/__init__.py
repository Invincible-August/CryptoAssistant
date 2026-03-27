"""
因子插件系统入口模块。
提供 register_all_factors() 函数，在应用启动时调用以
自动扫描并注册 builtins/ 和 custom/ 目录下的所有因子。
"""
from pathlib import Path

from loguru import logger

from app.factors.registry import FactorRegistry


def register_all_factors() -> int:
    """
    注册所有因子插件。

    自动扫描以下两个目录并注册发现的因子：
    1. builtins/ —— 系统内置因子（随项目发布）
    2. custom/   —— 用户自定义因子（人工编写或AI生成）

    此函数应在应用启动阶段调用一次。

    Returns:
        int: 总共注册成功的因子数量
    """
    logger.info("==================== 因子插件系统初始化 ====================")

    # 获取当前模块所在目录作为基准路径
    base_dir = Path(__file__).parent
    total_registered = 0

    # ---------- 扫描并注册内置因子 ----------
    builtins_path = str(base_dir / "builtins")
    builtins_count = FactorRegistry.scan_and_register(
        package_path=builtins_path,
        package_name="app.factors.builtins",
    )
    total_registered += builtins_count

    # ---------- 扫描并注册自定义因子 ----------
    custom_path = str(base_dir / "custom")
    custom_count = FactorRegistry.scan_and_register(
        package_path=custom_path,
        package_name="app.factors.custom",
    )
    total_registered += custom_count

    logger.info(
        f"因子插件系统初始化完成: "
        f"内置因子 {builtins_count} 个, "
        f"自定义因子 {custom_count} 个, "
        f"共计 {total_registered} 个"
    )
    logger.info("=" * 60)

    return total_registered

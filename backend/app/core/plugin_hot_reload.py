"""
Plugin hot-reload: evict indicator/factor plugin modules and rescan packages.

Unloads ``sys.modules`` entries under ``app.indicators.{builtins,custom}`` and
``app.factors.{builtins,custom}``, clears matching registry rows, then runs the
same registration routines as application startup.

Limitations:
    Cross-package import cycles between custom modules may require a second
    reload or a full process restart; see project README.
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from loguru import logger

from app.factors import register_all_factors
from app.factors.registry import FactorRegistry
from app.indicators import register_all_indicators
from app.indicators.registry import indicator_registry

# Top-level plugin trees that may be removed from sys.modules.
_PLUGIN_MODULE_ROOTS: tuple[str, ...] = (
    "app.indicators.builtins",
    "app.indicators.custom",
    "app.factors.builtins",
    "app.factors.custom",
)


def _collect_sys_modules_to_evict() -> List[str]:
    """
    Build the list of ``sys.modules`` keys to pop for plugin reload.

    Returns:
        Module names sorted longest-first so nested packages are cleared
        before parents when possible.
    """
    names: List[str] = []
    for root in _PLUGIN_MODULE_ROOTS:
        if root in sys.modules:
            names.append(root)
        prefix = f"{root}."
        names.extend(key for key in sys.modules if key.startswith(prefix))
    return sorted(set(names), key=len, reverse=True)


def reload_plugin_packages() -> Dict[str, Any]:
    """
    Perform a full plugin hot-reload cycle.

    Steps:
        1. Remove registry entries whose classes were defined under plugin roots.
        2. Pop matching entries from ``sys.modules``.
        3. Call ``register_all_indicators`` and ``register_all_factors``.

    Returns:
        Summary statistics for admin API consumers.
    """
    indicators_unregistered = indicator_registry.unregister_plugin_packages()
    factors_unregistered = FactorRegistry.unregister_plugin_packages()

    to_evict = _collect_sys_modules_to_evict()
    for module_name in to_evict:
        sys.modules.pop(module_name, None)

    logger.info(
        f"Plugin hot-reload: removed {len(to_evict)} sys.modules entries, "
        f"unregistered {indicators_unregistered} indicators / "
        f"{factors_unregistered} factors"
    )

    register_all_indicators()
    register_all_factors()

    indicator_keys = indicator_registry.list_keys()
    factor_total = FactorRegistry.count()

    return {
        "modules_evicted": len(to_evict),
        "indicators_unregistered": indicators_unregistered,
        "factors_unregistered": factors_unregistered,
        "indicator_count_after": len(indicator_keys),
        "factor_count_after": factor_total,
    }

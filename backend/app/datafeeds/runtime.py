"""
Datafeed runtime initialization.

This module is responsible for:
1) creating a singleton :class:`~app.datafeeds.manager.DatafeedManager`
2) registering exchange adapters (Binance for now; OKX/Bitget later)
3) connecting those adapters during application startup

So upper layers can just call:
    from app.datafeeds.runtime import datafeed_manager
    adapter = datafeed_manager.get_adapter("binance")
"""

from __future__ import annotations

from typing import Dict

from loguru import logger

from app.datafeeds.exchanges.binance.adapter import BinanceAdapter
from app.datafeeds.manager import DatafeedManager

# Singleton manager used by the whole backend process.
datafeed_manager = DatafeedManager()

# Avoid re-registering adapters on hot reload / multiple lifespan calls.
_initialized: bool = False


async def init_datafeeds() -> None:
    """
    Initialize and connect exchange adapters.

    Notes:
        - Only Binance is implemented in this repository right now.
        - OKX/Bitget can be added later by registering their adapters here.
    """
    global _initialized
    if _initialized:
        return

    adapters: Dict[str, object] = {}
    try:
        # --- Binance ---
        binance_adapter = BinanceAdapter()
        datafeed_manager.register_adapter(binance_adapter)
        adapters[binance_adapter.exchange_name] = binance_adapter
    except Exception as exc:  # noqa: BLE001
        logger.error("初始化数据源适配器失败: %s", exc, exc_info=True)

    # Connect adapters (connect is idempotent-ish at adapter level).
    for adapter in adapters.values():
        try:
            await adapter.connect()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "适配器连接失败: %s",
                exc,
                exc_info=True,
            )

    _initialized = True
    logger.info("数据源运行时初始化完成（当前仅 Binance）")


"""
种子数据脚本。
为开发和测试环境生成示例数据。
用法: python scripts/seed_demo_data.py
"""
import asyncio
import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import select, delete
from app.core.database import async_session_factory, init_db
from app.models.module_config import ModuleConfig
from app.models.symbol_watch import SymbolWatch
from app.models.market_kline import MarketKline


async def seed_module_configs(session):
    """
    初始化模块配置。
    先检查是否已有数据，有则跳过，避免重复插入导致唯一约束冲突。
    """
    existing = await session.execute(select(ModuleConfig).limit(1))
    if existing.scalar_one_or_none():
        print("[跳过] 模块配置已存在，无需重复插入")
        return

    modules = [
        {"module_name": "ai", "enabled": False, "config_json": {"model": "gpt-4"}},
        {"module_name": "tradingview", "enabled": False, "config_json": {}},
        {"module_name": "execution", "enabled": False, "config_json": {"mode": "simulated"}},
        {"module_name": "backtest", "enabled": True, "config_json": {}},
        {"module_name": "exchange_binance", "enabled": True, "config_json": {"testnet": True}},
    ]

    for m in modules:
        config = ModuleConfig(**m)
        session.add(config)

    print(f"[成功] 已插入 {len(modules)} 条模块配置")


async def seed_symbol_watches(session):
    """
    初始化监控标的。
    先检查是否已有数据，有则跳过。
    """
    existing = await session.execute(select(SymbolWatch).limit(1))
    if existing.scalar_one_or_none():
        print("[跳过] 监控标的已存在，无需重复插入")
        return

    watches = [
        {"exchange": "binance", "symbol": "BTCUSDT", "market_type": "spot", "event_type": "all", "watch_status": "active"},
        {"exchange": "binance", "symbol": "ETHUSDT", "market_type": "spot", "event_type": "all", "watch_status": "active"},
        {"exchange": "binance", "symbol": "BTCUSDT", "market_type": "perp", "event_type": "all", "watch_status": "active"},
    ]

    for w in watches:
        watch = SymbolWatch(**w, config_json={})
        session.add(watch)

    print(f"[成功] 已插入 {len(watches)} 条监控标的")


async def seed_sample_klines(session):
    """
    生成示例K线数据（用于回测测试）。
    先清除旧的示例K线数据再重新生成，确保可重复运行。
    使用不带时区的 datetime（与数据库 TIMESTAMP WITHOUT TIME ZONE 匹配）。
    """
    symbol = "BTCUSDT"
    exchange = "binance"
    market_type = "spot"
    interval = "1h"

    # 清除旧的示例K线，确保脚本可安全地重复运行
    await session.execute(
        delete(MarketKline).where(
            MarketKline.exchange == exchange,
            MarketKline.symbol == symbol,
            MarketKline.market_type == market_type,
            MarketKline.interval == interval,
        )
    )
    print("[清理] 已清除旧的示例K线数据")

    # 使用不带时区信息的 UTC 时间，与数据库 DateTime 列类型匹配
    now = datetime.utcnow()
    start_time = now - timedelta(days=30)

    base_price = 65000.0
    current_price = base_price
    count = 0

    current_time = start_time
    while current_time < now:
        # 模拟价格随机游走（高斯分布，标准差0.5%）
        change = random.gauss(0, 0.005)
        current_price *= 1 + change

        open_price = current_price
        high_price = open_price * (1 + abs(random.gauss(0, 0.003)))
        low_price = open_price * (1 - abs(random.gauss(0, 0.003)))
        close_price = open_price * (1 + random.gauss(0, 0.002))
        volume = random.uniform(100, 5000)

        kline = MarketKline(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            interval=interval,
            open_time=current_time,
            close_time=current_time + timedelta(hours=1),
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=round(volume, 4),
            quote_volume=round(volume * close_price, 2),
            trade_count=random.randint(500, 10000),
        )
        session.add(kline)
        current_time += timedelta(hours=1)
        count += 1

    print(f"[成功] 已生成 {count} 根 {symbol} {interval} K线数据")


async def main():
    """主函数：依次初始化模块配置、监控标的和示例K线"""
    print("=" * 50)
    print("  种子数据初始化")
    print("=" * 50)

    await init_db()

    async with async_session_factory() as session:
        await seed_module_configs(session)
        await seed_symbol_watches(session)
        await seed_sample_klines(session)
        await session.commit()

    print("\n[完成] 所有种子数据已插入")


if __name__ == "__main__":
    asyncio.run(main())

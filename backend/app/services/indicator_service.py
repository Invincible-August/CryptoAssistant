"""
技术指标服务模块。
提供指标注册、计算和结果查询的业务逻辑。

职责链路：
1. 从指标注册中心获取可用指标列表
2. 调用数据服务获取计算所需的原始K线数据
3. 调用指标的 calculate 方法执行计算
4. 将计算结果持久化到数据库
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.indicators.registry import indicator_registry
from app.services.plugin_runtime_service import get_plugin_runtime_service
from app.services.market_data_provider import market_data_provider, SourceMode
from app.models.indicator_definition import IndicatorDefinition
from app.models.indicator_result import IndicatorResult
from app.models.market_kline import MarketKline


async def list_indicators() -> List[Dict[str, Any]]:
    """
    列出所有已注册的技术指标及其元数据。

    从内存中的指标注册中心获取，不涉及数据库查询。

    Returns:
        指标元数据字典列表，每项包含 indicator_key / name / category 等
    """
    indicators = indicator_registry.list_all()
    logger.debug(f"已注册指标总数: {len(indicators)}")
    return indicators


async def calculate_indicator(
    db: AsyncSession,
    indicator_key: str,
    exchange: str,
    symbol: str,
    market_type: str,
    timeframe: str,
    params: Optional[Dict[str, Any]] = None,
    limit: int = 500,
    source_mode: SourceMode = "cache",
) -> Dict[str, Any]:
    """
    计算指定技术指标并保存结果。

    完整流程：
    1. 从注册中心获取指标类
    2. 校验并补全参数
    3. 从数据库加载历史K线数据
    4. 将K线转换为 DataFrame 调用指标计算方法
    5. 将计算结果持久化到 IndicatorResult 表

    Args:
        db: 异步数据库会话
        indicator_key: 指标唯一标识（如 "rsi", "macd"）
        exchange: 交易所标识
        symbol: 交易对
        market_type: 市场类型
        timeframe: 计算时间帧（如 "1h", "4h"）
        params: 指标计算参数（如 {"period": 14}），可选
        limit: 加载K线数据的条数

    Returns:
        计算结果字典，包含 indicator_key / result_count / latest_result 等

    Raises:
        KeyError: 指标未在注册中心注册
        ValueError: 参数校验失败或无可用K线数据
    """
    runtime = get_plugin_runtime_service()
    if not runtime.is_indicator_load_enabled(indicator_key):
        raise ValueError(f"指标已禁用（不加载）: {indicator_key}")

    # 从注册中心获取指标类（不存在会抛出 KeyError）
    indicator_cls = indicator_registry.get(indicator_key)

    # 校验并补全参数
    validated_params = indicator_cls.validate_params(params or {})

    # 加载历史K线数据（cache/live 统一入口）
    klines = await market_data_provider.get_klines(
        db,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        interval=timeframe,
        limit=limit,
        source_mode=source_mode,
        persist_to_db=(source_mode == "live"),
    )

    if not klines:
        raise ValueError(
            f"没有可用的K线数据: {symbol} {timeframe}，请先采集数据"
        )

    # 将 ORM 对象转换为 pandas DataFrame，供指标计算使用
    kline_df = pd.DataFrame(
        [
            {
                "open_time": k["open_time"],
                "open": k["open"],
                "high": k["high"],
                "low": k["low"],
                "close": k["close"],
                "volume": k.get("volume", 0.0),
                "quote_volume": k.get("quote_volume", 0.0),
                "trade_count": k.get("trade_count", 0),
            }
            for k in klines
        ]
    )

    logger.info(
        f"开始计算指标: {indicator_key}，"
        f"数据量: {len(kline_df)} 条 ({symbol} {timeframe})"
    )

    # 执行指标计算
    result_df = indicator_cls.calculate(kline_df, validated_params)

    # 将计算结果保存到数据库
    saved_count = 0
    for _, row in result_df.iterrows():
        indicator_result = IndicatorResult(
            exchange=exchange,
            symbol=symbol,
            market_type=market_type,
            indicator_key=indicator_key,
            source=indicator_cls.source,
            timeframe=timeframe,
            event_time=row.get("open_time", datetime.utcnow()),
            result_json=row.to_dict(),
        )
        db.add(indicator_result)
        saved_count += 1

    await db.flush()

    # 获取最新一条结果
    latest_result = result_df.iloc[-1].to_dict() if not result_df.empty else None

    logger.info(
        f"指标计算完成: {indicator_key}，"
        f"保存 {saved_count} 条结果"
    )

    return {
        "indicator_key": indicator_key,
        "symbol": symbol,
        "timeframe": timeframe,
        "result_count": saved_count,
        "latest_result": latest_result,
    }


async def get_indicator_results(
    db: AsyncSession,
    symbol: str,
    indicator_key: str,
    exchange: str = "binance",
    market_type: str = "spot",
    timeframe: str = "1h",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
) -> List[IndicatorResult]:
    """
    查询指标计算结果历史记录。

    Args:
        db: 异步数据库会话
        symbol: 交易对
        indicator_key: 指标唯一标识
        exchange: 交易所标识
        market_type: 市场类型
        timeframe: 时间帧
        start_time: 起始时间过滤（可选）
        end_time: 结束时间过滤（可选）
        limit: 返回最大条数

    Returns:
        IndicatorResult 对象列表
    """
    query = select(IndicatorResult).where(
        and_(
            IndicatorResult.exchange == exchange,
            IndicatorResult.symbol == symbol,
            IndicatorResult.market_type == market_type,
            IndicatorResult.indicator_key == indicator_key,
            IndicatorResult.timeframe == timeframe,
        )
    )

    if start_time:
        query = query.where(IndicatorResult.event_time >= start_time)
    if end_time:
        query = query.where(IndicatorResult.event_time <= end_time)

    query = query.order_by(desc(IndicatorResult.event_time)).limit(limit)

    result = await db.execute(query)
    results = list(result.scalars().all())

    logger.debug(
        f"指标结果查询: {indicator_key} {symbol} {timeframe}，"
        f"返回 {len(results)} 条"
    )
    return results


async def register_indicator_from_db(db: AsyncSession) -> int:
    """
    从数据库加载指标定义并注册到内存注册中心。

    适用场景：系统启动时从数据库同步那些通过 AI 或 Web 界面
    动态创建的指标定义，补充到内存注册中心。

    注意：此方法仅加载元数据，不加载计算代码。
    动态指标的计算逻辑需通过 code_path 字段指定的模块路径加载。

    Args:
        db: 异步数据库会话

    Returns:
        本次成功注册的指标数量
    """
    # 查询所有启用的、非内置的指标定义
    query = select(IndicatorDefinition).where(
        and_(
            IndicatorDefinition.enabled == True,
            IndicatorDefinition.source != "builtin",
        )
    )

    result = await db.execute(query)
    definitions = list(result.scalars().all())

    registered_count = 0
    for definition in definitions:
        try:
            # 检查是否已在注册中心（避免重复注册）
            existing_keys = indicator_registry.list_keys()
            if definition.indicator_key in existing_keys:
                continue

            logger.info(
                f"从数据库加载指标定义: {definition.indicator_key} "
                f"(来源={definition.source})"
            )
            registered_count += 1

        except Exception as load_error:
            logger.error(
                f"从数据库注册指标失败: {definition.indicator_key} - "
                f"{load_error}"
            )

    logger.info(f"从数据库同步指标定义完成，新注册 {registered_count} 个")
    return registered_count

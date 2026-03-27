"""
分析服务模块。
编排完整的市场分析流程：数据获取→指标计算→因子计算→评分→推断→建议。
"""
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from loguru import logger
import pandas as pd

from app.models.market_kline import MarketKline
from app.models.analysis_snapshot import AnalysisSnapshot
from app.models.signal_recommendation import SignalRecommendation
from app.modules.feature_pipeline import FeaturePipeline
from app.modules.scoring_engine import ScoringEngine
from app.modules.hypothesis_engine import HypothesisEngine
from app.modules.recommendation_engine import RecommendationEngine


async def run_full_analysis(
    db: AsyncSession,
    symbol: str,
    exchange: str = "binance",
    market_type: str = "spot",
    timeframe: str = "1h",
) -> Dict[str, Any]:
    """
    运行完整的市场分析流程。

    流程：
    1. 加载最新K线数据
    2. 运行特征管线（计算指标和因子）
    3. 运行评分引擎
    4. 运行行为推断引擎
    5. 运行建议生成引擎
    6. 保存分析快照和建议到数据库

    Args:
        db: 数据库会话
        symbol: 交易对
        exchange: 交易所
        market_type: 市场类型
        timeframe: K线周期

    Returns:
        完整分析结果
    """
    logger.info(f"开始分析: {symbol} ({exchange}/{market_type}/{timeframe})")

    # 第一步：加载K线数据
    result = await db.execute(
        select(MarketKline)
        .where(
            MarketKline.symbol == symbol,
            MarketKline.exchange == exchange,
            MarketKline.market_type == market_type,
            MarketKline.interval == timeframe,
        )
        .order_by(desc(MarketKline.open_time))
        .limit(300)
    )
    klines = result.scalars().all()

    if len(klines) < 60:
        logger.warning(f"K线数据不足: {symbol} 仅有 {len(klines)} 根")
        return {
            "status": "insufficient_data",
            "message": f"K线数据不足（{len(klines)}/60），请先导入历史数据",
            "symbol": symbol,
        }

    # 按时间正序排列
    klines.reverse()
    kline_data = [
        {
            "open_time": k.open_time,
            "open": float(k.open) if k.open else 0,
            "high": float(k.high) if k.high else 0,
            "low": float(k.low) if k.low else 0,
            "close": float(k.close) if k.close else 0,
            "volume": float(k.volume) if k.volume else 0,
        }
        for k in klines
    ]
    kline_df = pd.DataFrame(kline_data)

    # 第二步：运行特征管线
    pipeline = FeaturePipeline()
    pipeline.set_enabled_indicators(["ema", "rsi", "macd", "vwap"])
    pipeline.set_enabled_factors(["momentum", "volatility", "trade_delta"])

    features = await pipeline.run_full_pipeline(kline_df)

    # 第三步：评分
    scoring = ScoringEngine()
    scores = scoring.compute_scores(features.get("factor_results", {}))

    # 第四步：行为推断
    hypothesis = HypothesisEngine()
    behavior = hypothesis.analyze(scores)

    # 第五步：生成建议
    rec_engine = RecommendationEngine()
    current_price = float(kline_df.iloc[-1]["close"])
    recommendation = rec_engine.generate(scores, behavior, current_price)

    # 保存分析快照
    now = datetime.now(timezone.utc)
    snapshot = AnalysisSnapshot(
        exchange=exchange,
        symbol=symbol,
        market_type=market_type,
        event_time=now,
        stage=behavior.get("stage", "unknown"),
        estimated_cost_zone=behavior.get("estimated_cost_zone"),
        scores_json=scores,
        hypotheses_json=behavior.get("hypotheses", []),
        evidence_json=behavior.get("evidence", []),
        risks_json=behavior.get("risks", []),
        summary=behavior.get("summary", ""),
    )
    db.add(snapshot)
    await db.flush()

    # 保存建议
    signal = SignalRecommendation(
        analysis_snapshot_id=snapshot.id,
        exchange=exchange,
        symbol=symbol,
        direction=recommendation.get("direction", "neutral"),
        confidence=recommendation.get("confidence", 0),
        win_rate=recommendation.get("win_rate", 0),
        entry_zone=recommendation.get("entry_zone"),
        stop_loss=recommendation.get("stop_loss", 0),
        take_profits=recommendation.get("take_profits"),
        tp_strategy=recommendation.get("tp_strategy"),
        risks_json=recommendation.get("risks", []),
        reasons_json=recommendation.get("reasons", []),
        summary=recommendation.get("summary", ""),
    )
    db.add(signal)
    await db.flush()

    logger.info(f"分析完成: {symbol}, 阶段={behavior.get('stage')}, 方向={recommendation.get('direction')}")

    return {
        "status": "success",
        "symbol": symbol,
        "analysis_snapshot_id": snapshot.id,
        "behavior_profile": behavior,
        "scores": scores,
        "recommendation": recommendation,
        "current_price": current_price,
        "analyzed_at": now.isoformat(),
    }

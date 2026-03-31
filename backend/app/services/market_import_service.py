"""
Background market data import orchestration.

Loads ``MarketImportTask`` configuration from the database, pulls historical data
through an exchange provider (Binance by default), and persists rows via
``market_service.save_*`` helpers with idempotent semantics where supported.

Open-interest imports are cropped to the latest 30 days; aggregate trades are
fetched in <=1 hour windows to satisfy Binance ``aggTrades`` constraints.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.datafeeds.exchanges.binance.parser import (
    parse_rest_funding_rate_history,
    parse_rest_klines,
    parse_rest_open_interest_history,
    parse_rest_agg_trades,
)
from app.datafeeds.exchanges.binance.rest_client import BinanceRestClient
from app.models.market_import_task import MarketImportTask
from app.services import market_service

# -----------------------------------------------------------------------------
# Constants (MVP assumptions)
# -----------------------------------------------------------------------------

# Binance futures ``aggTrades`` historical window must be <= 1 hour (spec).
TRADE_CHUNK_MS_MS: int = 3_600_000

# Open-interest history API only guarantees meaningful coverage for recent data.
OI_LOOKBACK_DAYS: int = 30

# Kline REST limits (Binance spot 1000, USDT-M futures 1500).
_KLINE_LIMIT_SPOT: int = 1000
_KLINE_LIMIT_FUTURES: int = 1500

# Funding history batch limit (Binance caps at 1000).
_FUNDING_BATCH_LIMIT: int = 1000

# Open-interest history batch limit (Binance default max 500 on this endpoint).
_OI_BATCH_LIMIT: int = 500

# Type key aliases from API / UI.
_IMPORT_TYPE_ALIASES: Dict[str, str] = {
    "trade": "trades",
    "trades": "trades",
    "kline": "kline",
    "funding": "funding_rate",
    "funding_rate": "funding_rate",
    "open_interest": "open_interest",
    "oi": "open_interest",
    "orderbook": "orderbook",
}

_PROCESS_ORDER: Tuple[str, ...] = (
    "kline",
    "trades",
    "funding_rate",
    "open_interest",
    "orderbook",
)

_SUPPORTED_IMPORT_TYPES: frozenset[str] = frozenset(_PROCESS_ORDER)

# -----------------------------------------------------------------------------
# Import type capability table (min granularity & progress estimation)
# -----------------------------------------------------------------------------
#
# 说明（中文）：
# - 前端/任务表里的 `task.timeframe` 是“请求意图”，但并不等于交易所接口真实可用粒度。
# - 为保证导入执行器行为稳定可预期，这里定义每个 import type 的“能力表/最小可用粒度”。
# - Task3 规则：
#   - kline: 永远用 1m 拉取（即使 task.timeframe 不是 1m，也不能向上采样/插值）
#   - open_interest: 用 Binance 可用的最小 period（当前为 5m），不做 1m 插值/对齐
#   - funding_rate: 按事件粒度拉取（通常 8h/次），不插值
#
# 设计要点：
# - 把“有效粒度”写入 result_json，便于 UI/排障/回放任务。
# - 进度估算也基于“有效粒度”，避免 timeframe 被上层强制/误传导致进度跳变。
_IMPORT_TYPE_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "kline": {
        "mode": "fixed_interval",
        "effective_interval": "1m",
        # kline 进度估算用 1m 间隔
        "progress_interval_ms": 60_000,
    },
    "open_interest": {
        "mode": "min_period",
        # Binance openInterestHist 最小 period；与 task.timeframe 无关
        "effective_period": "5m",
        "progress_interval_ms": 5 * 60_000,
    },
    "funding_rate": {
        "mode": "event_based",
        # Binance fundingRate 通常每 8 小时一条（不保证严格固定，但用于估算/说明足够）
        "effective_period": "8h",
        "progress_interval_ms": 8 * 3_600_000,
    },
    # 其他类型先留空白能力（便于未来扩展）
    "trades": {"mode": "chunked"},
    "orderbook": {"mode": "unsupported_historical"},
}


def _cap(kind: str) -> Dict[str, Any]:
    """
    Return capability info for an import kind.

    Args:
        kind: Canonical import type key.

    Returns:
        Capability dict (empty when unknown).
    """
    return dict(_IMPORT_TYPE_CAPABILITIES.get(kind, {}))


def _effective_granularity_for_task(task: MarketImportTask, kind: str) -> Dict[str, Any]:
    """
    Compute the effective data granularity for an import type.

    说明（中文）：
    - 这里是“真正向交易所请求数据时使用的粒度”，用于强制最小粒度降级，
      以及写入 result_json 供前端展示。
    - 该函数不做插值/重采样；只返回“实际请求参数”。

    Args:
        task: Import task row.
        kind: Import type key.

    Returns:
        Dict including effective_interval/effective_period and a short explanation.
    """
    c = _cap(kind)
    mode = c.get("mode")
    if kind == "kline":
        return {
            "mode": mode,
            "effective_interval": c.get("effective_interval", "1m"),
            "explain": "kline 永远按 1m 拉取；不随 task.timeframe 改变",
        }
    if kind == "open_interest":
        return {
            "mode": mode,
            "effective_period": c.get("effective_period", "5m"),
            "explain": "open_interest 使用交易所最小 period；不做 1m 插值/对齐",
        }
    if kind == "funding_rate":
        return {
            "mode": mode,
            "effective_period": c.get("effective_period", "8h"),
            "explain": "funding_rate 按事件粒度拉取（通常 8h）；不插值",
        }
    return {"mode": mode or "unknown", "explain": "no capability rule defined"}


def normalize_import_types(raw: List[str]) -> List[str]:
    """
    Normalize import type strings to canonical keys and preserve stable order.

    Args:
        raw: Raw import type labels from the client.

    Returns:
        De-duplicated canonical type keys in MVP processing order.
    """
    seen: set[str] = set()
    ordered: List[str] = []
    for item in raw:
        key = _IMPORT_TYPE_ALIASES.get(item.strip().lower(), item.strip().lower())
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    ordered = [t for t in ordered if t in _SUPPORTED_IMPORT_TYPES]
    rank = {k: i for i, k in enumerate(_PROCESS_ORDER)}
    ordered.sort(key=lambda x: (rank.get(x, 99), x))
    return ordered


def iter_trade_time_chunks_ms(
    start_ms: int,
    end_exclusive_ms: int,
    chunk_ms: int,
) -> List[Tuple[int, int]]:
    """
    Split ``[start_ms, end_exclusive_ms)`` into half-open windows of at most ``chunk_ms``.

    Args:
        start_ms: Inclusive range start (milliseconds).
        end_exclusive_ms: Exclusive range end (milliseconds).
        chunk_ms: Maximum window length in milliseconds.

    Returns:
        List of ``(window_start_ms, window_end_exclusive_ms)`` pairs.
    """
    if end_exclusive_ms <= start_ms:
        return []
    chunks: List[Tuple[int, int]] = []
    cursor = start_ms
    while cursor < end_exclusive_ms:
        nxt = min(cursor + chunk_ms, end_exclusive_ms)
        chunks.append((cursor, nxt))
        cursor = nxt
    return chunks


def crop_open_interest_range(
    request_start: datetime,
    request_end: datetime,
    now: datetime,
) -> Tuple[datetime, datetime, bool]:
    """
    Crop the user-requested range to ``[now-30d, now]`` for OI history.

    Args:
        request_start: Requested inclusive start (timezone-aware).
        request_end: Requested inclusive end (timezone-aware).
        now: Reference "current" instant (timezone-aware), injected for tests.

    Returns:
        Tuple of ``(effective_start, effective_end, partial)`` where ``partial``
        is True when the request extended outside the allowed window.
    """
    window_start = now - timedelta(days=OI_LOOKBACK_DAYS)
    effective_start = max(request_start, window_start)
    effective_end = min(request_end, now)
    partial = (request_start < window_start) or (request_end > now)
    if effective_start > effective_end:
        partial = True
    return effective_start, effective_end, partial


def apply_progress_monotonic(task: MarketImportTask, value: float) -> None:
    """
    Set ``task.progress`` to ``value`` clamped to [0,1] without decreasing it.

    Args:
        task: ORM task row being updated.
        value: Desired progress fraction.
    """
    clamped = max(0.0, min(1.0, float(value)))
    task.progress = max(float(task.progress or 0.0), clamped)


class TaskProgressLogger:
    """
    Throttled progress logger for market import tasks.

    This helper logs progress updates at most once per 5 seconds per task_id and
    enforces monotonic (non-decreasing) progress.
    """

    def __init__(
        self,
        *,
        logger: Any = logger,
        now_fn: Optional[Callable[[], datetime]] = None,
        throttle_seconds: float = 5.0,
    ) -> None:
        """
        Create a new progress logger.

        Args:
            logger: Logger-like object exposing ``info(message, *args)``.
            now_fn: Injectable time source for production callers (optional).
            throttle_seconds: Minimum seconds between logs per task_id.
        """

        # 说明（中文）：
        # - 为了让单测不依赖真实时间，这里把时间源抽象为可注入 now_fn。
        # - 在 maybe_log/flush 中也支持显式传入 now，测试可直接传固定时间点。
        self._logger = logger
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._throttle_seconds = float(throttle_seconds)

        # 说明（中文）：
        # - 按 task_id 维度节流：同一 task 5 秒内最多输出 1 条。
        # - progress 必须单调不下降：回退的 progress 不输出且不覆盖 last_progress。
        self._last_log_at_by_task_id: Dict[int, datetime] = {}
        self._last_progress_by_task_id: Dict[int, float] = {}

    def maybe_log(
        self,
        *,
        task: Any,
        import_type: str,
        progress_0_1: float,
        now: Optional[datetime] = None,
        force: bool = False,
    ) -> bool:
        """
        Log a progress line when allowed by throttle and monotonic rules.

        Args:
            task: Object with ``id``, ``name`` (optional), and ``symbol``.
            import_type: Import type key (e.g. kline/trades/open_interest).
            progress_0_1: Progress fraction in [0,1].
            now: Current time instant (timezone-aware). If omitted, uses ``now_fn``.
            force: When True, bypass throttle and always log (still clamps progress).

        Returns:
            True if a log line was emitted, else False.
        """
        task_id = int(getattr(task, "id"))
        task_name = getattr(task, "name", None) or f"market_import_{task_id}"
        symbol = getattr(task, "symbol", "")

        ts = now or self._now_fn()
        clamped = max(0.0, min(1.0, float(progress_0_1)))

        last_progress = float(self._last_progress_by_task_id.get(task_id, 0.0))
        if clamped < last_progress and not force:
            return False

        # 说明（中文）：即使节流导致本次不输出，也要记住“最新的最高进度”，避免下一次输出落后。
        if clamped >= last_progress:
            self._last_progress_by_task_id[task_id] = clamped

        if not force:
            last_log_at = self._last_log_at_by_task_id.get(task_id)
            if last_log_at is not None:
                delta_s = (ts - last_log_at).total_seconds()
                if delta_s < self._throttle_seconds:
                    return False

        self._last_log_at_by_task_id[task_id] = ts
        percent = int(clamped * 100)
        self._logger.info(
            "Market import progress task={} symbol={} import_type={} progress={}%",
            task_name,
            symbol,
            import_type,
            percent,
        )
        return True

    def flush(
        self,
        *,
        task: Any,
        import_type: str,
        now: Optional[datetime] = None,
    ) -> bool:
        """
        Force emit a 100% progress log for a task.

        说明（中文）：用于任务结束时强制输出一条 100%，避免最后一次日志被节流吞掉。
        """
        ts = now or self._now_fn()
        return self.maybe_log(
            task=task,
            import_type=import_type,
            progress_0_1=1.0,
            now=ts,
            force=True,
        )


def build_result_json(
    summary: Dict[str, Any],
    type_results: Dict[str, Any],
    errors: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the persisted ``result_json`` payload (MVP schema).

    Args:
        summary: High-level counters and labels.
        type_results: Per-import-type status and metrics.
        errors: Structured error list.

    Returns:
        JSON-serializable dict for ``MarketImportTask.result_json``.
    """
    return {
        "summary": summary,
        "type_results": type_results,
        "errors": errors,
    }


def _interval_to_milliseconds(interval: str) -> int:
    """
    Map a Binance-style interval label to its length in milliseconds.

    Args:
        interval: Interval string such as ``1m`` or ``1h``.

    Returns:
        Positive duration in milliseconds; defaults to 1h if unknown.
    """
    s = interval.strip().lower()
    if s.endswith("ms"):
        return max(1, int(s[:-2]))
    if s.endswith("m"):
        return int(s[:-1]) * 60_000
    if s.endswith("h"):
        return int(s[:-1]) * 3_600_000
    if s.endswith("d"):
        return int(s[:-1]) * 86_400_000
    if s.endswith("w"):
        return int(s[:-1]) * 604_800_000
    return 3_600_000


def _timeframe_to_open_interest_period(timeframe: str) -> str:
    """
    Map kline-style timeframe to a Binance ``openInterestHist`` ``period`` value.

    Args:
        timeframe: Task timeframe (e.g. ``1m``, ``1h``).

    Returns:
        Supported ``period`` string for the OI history endpoint.
    """
    tf = timeframe.strip().lower()
    mapping = {
        "1m": "5m",
        "3m": "5m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "2h": "1h",
        "4h": "1h",
        "6h": "1h",
        "12h": "1h",
        "1d": "1d",
    }
    return mapping.get(tf, "1h")


def _parser_market_type(task_market_type: str) -> str:
    """Map persisted ``market_type`` to parser labels (``spot`` / ``perp``)."""
    return "spot" if task_market_type == "spot" else "perp"


def _inclusive_end_to_exclusive_ms(end_inclusive: datetime) -> int:
    """Convert inclusive end datetime to exclusive end in milliseconds."""
    return int(end_inclusive.timestamp() * 1000) + 1


@runtime_checkable
class MarketImportExchangePort(Protocol):
    """Exchange-facing port for unit tests (mock) and Binance implementation."""

    async def fetch_klines_window(
        self,
        *,
        symbol: str,
        market_type: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        limit: int,
    ) -> List[List[Any]]:
        ...

    async def fetch_agg_trades_window(
        self,
        *,
        symbol: str,
        market_type: str,
        start_ms: int,
        end_ms: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        ...

    async def fetch_funding_rate_history(
        self,
        *,
        symbol: str,
        start_ms: int,
        end_ms: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        ...

    async def fetch_open_interest_history(
        self,
        *,
        symbol: str,
        period: str,
        start_ms: Optional[int],
        end_ms: Optional[int],
        limit: int,
    ) -> List[Dict[str, Any]]:
        ...


class BinanceMarketImportExchange:
    """
    Binance REST implementation of :class:`MarketImportExchangePort`.

    Uses :class:`BinanceRestClient` and existing parsers to return normalized
    rows suitable for ``market_service.save_*`` helpers.
    """

    def __init__(self, rest_client: Optional[BinanceRestClient] = None) -> None:
        """
        Initialize the Binance-backed import exchange.

        Args:
            rest_client: Optional REST client (defaults to a new instance).
        """
        self._rest = rest_client or BinanceRestClient()

    async def fetch_klines_window(
        self,
        *,
        symbol: str,
        market_type: str,
        interval: str,
        start_ms: int,
        end_ms: int,
        limit: int,
    ) -> List[List[Any]]:
        """Fetch one REST batch of raw kline arrays for the given window."""
        if market_type == "spot":
            return await self._rest.get_spot_klines(
                symbol,
                interval,
                limit=min(limit, _KLINE_LIMIT_SPOT),
                start_time=start_ms,
                end_time=end_ms,
            )
        return await self._rest.get_futures_klines(
            symbol,
            interval,
            limit=min(limit, _KLINE_LIMIT_FUTURES),
            start_time=start_ms,
            end_time=end_ms,
        )

    async def fetch_agg_trades_window(
        self,
        *,
        symbol: str,
        market_type: str,
        start_ms: int,
        end_ms: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Fetch aggregate trades for ``[start_ms, end_ms)`` and normalize rows.

        Args:
            symbol: Trading pair.
            market_type: ``spot`` or ``futures`` (stored market type).
            start_ms: Window start in milliseconds.
            end_ms: Exclusive window end in milliseconds.
            limit: Max trades per request.

        Returns:
            Dict rows including ``event_time`` as ISO strings for downstream parsing.
        """
        mt = _parser_market_type(market_type)
        if mt == "spot":
            raw = await self._rest.get_spot_agg_trades(
                symbol,
                start_time=start_ms,
                end_time=end_ms,
                limit=limit,
            )
        else:
            raw = await self._rest.get_futures_agg_trades(
                symbol,
                start_time=start_ms,
                end_time=end_ms,
                limit=limit,
            )
        trades = parse_rest_agg_trades(raw, "binance", symbol, mt)
        return [
            {
                "exchange": t.exchange,
                "symbol": t.symbol,
                "market_type": market_type,
                "trade_id": t.trade_id,
                "price": str(t.price),
                "quantity": str(t.quantity),
                "side": t.side,
                "event_time": t.event_time,
            }
            for t in trades
        ]

    async def fetch_funding_rate_history(
        self,
        *,
        symbol: str,
        start_ms: int,
        end_ms: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fetch normalized funding rate history rows."""
        raw = await self._rest.get_funding_rate_history(
            symbol,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit,
        )
        return parse_rest_funding_rate_history(raw, "binance")

    async def fetch_open_interest_history(
        self,
        *,
        symbol: str,
        period: str,
        start_ms: Optional[int],
        end_ms: Optional[int],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Fetch normalized open-interest history rows."""
        raw = await self._rest.get_open_interest_history(
            symbol,
            period=period,
            start_time=start_ms,
            end_time=end_ms,
            limit=limit,
        )
        return parse_rest_open_interest_history(raw, "binance")


class MarketImportService:
    """
    Orchestrates long-running market imports for :class:`MarketImportTask` rows.

    Attributes:
        exchange: Data provider implementing :class:`MarketImportExchangePort`.
        save_trade_fn: Injectable ``save_trade`` for unit tests.
        save_kline_fn: Injectable ``save_kline`` for unit tests.
        save_funding_fn: Injectable ``save_funding`` for unit tests.
        save_open_interest_fn: Injectable ``save_open_interest`` for unit tests.
    """

    def __init__(
        self,
        exchange: Optional[MarketImportExchangePort] = None,
        *,
        save_trade_fn: Optional[Callable[..., Any]] = None,
        save_kline_fn: Optional[Callable[..., Any]] = None,
        save_funding_fn: Optional[Callable[..., Any]] = None,
        save_open_interest_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        """
        Initialize the import service.

        Args:
            exchange: Optional exchange port (defaults to :class:`BinanceMarketImportExchange`).
            save_trade_fn: Optional override for trade persistence.
            save_kline_fn: Optional override for kline persistence.
            save_funding_fn: Optional override for funding persistence.
            save_open_interest_fn: Optional override for OI persistence.
        """
        self.exchange = exchange or BinanceMarketImportExchange()
        self.save_trade_fn = save_trade_fn or market_service.save_trade
        self.save_kline_fn = save_kline_fn or market_service.save_kline
        self.save_funding_fn = save_funding_fn or market_service.save_funding
        self.save_open_interest_fn = (
            save_open_interest_fn or market_service.save_open_interest
        )

    async def run_import_task(self, task_id: int) -> None:
        """
        Load a task and execute import logic using a fresh DB session.

        This entrypoint is intended for ``asyncio.create_task`` background runs.

        Args:
            task_id: Primary key of :class:`MarketImportTask`.
        """
        try:
            async with async_session_factory() as session:
                await self.run_import_with_session(session, task_id)
                await session.commit()
        except Exception as exc:  # noqa: BLE001 — top-level worker must not crash silently
            logger.exception("Market import task {} failed: {}", task_id, exc)
            async with async_session_factory() as session:
                task = await self._load_task(session, task_id)
                if task is not None:
                    task.status = "failed"
                    task.last_error = str(exc)[:2048]
                    task.finished_at = datetime.now(timezone.utc)
                    apply_progress_monotonic(task, task.progress)
                    if task.result_json is None:
                        task.result_json = build_result_json(
                            summary={
                                "import_types_requested": [],
                                "import_types_completed": [],
                                "rows_total": 0,
                            },
                            type_results={},
                            errors=[{"type": "fatal", "message": str(exc)[:2048]}],
                        )
                    await session.commit()

    async def run_import_with_session(
        self,
        session: AsyncSession,
        task_id: int,
    ) -> None:
        """
        Execute import for ``task_id`` using the provided session.

        Args:
            session: Active async SQLAlchemy session.
            task_id: Task primary key.
        """
        task = await self._load_task(session, task_id)
        if task is None:
            logger.warning("Market import task not found: {}", task_id)
            return

        now = datetime.now(timezone.utc)
        task.status = "running"
        apply_progress_monotonic(task, 0.0)
        progress_logger = TaskProgressLogger()
        session.add(task)
        # Persist running/progress state so polling can observe it.
        await session.flush()
        await session.commit()

        type_results: Dict[str, Any] = {}
        errors: List[Dict[str, Any]] = []
        rows_total = 0

        requested = normalize_import_types(list(task.import_types or []))
        summary_requested = list(requested)

        completed_units = 0
        total_units = self._estimate_total_units(task, requested, now)
        total_units = max(1, total_units)

        def bump(kind: str) -> None:
            nonlocal completed_units
            completed_units += 1
            denom = max(total_units, completed_units)
            apply_progress_monotonic(task, 0.05 + 0.9 * (completed_units / denom))
            progress_logger.maybe_log(
                task=task,
                import_type=kind,
                progress_0_1=float(task.progress or 0.0),
                now=datetime.now(timezone.utc),
            )

        for kind in requested:
            if kind == "kline":
                n, tr = await self._import_klines(
                    session, task, bump=lambda: bump("kline")
                )
                rows_total += n
                type_results["kline"] = tr
            elif kind == "trades":
                n, tr = await self._import_trades(
                    session, task, bump=lambda: bump("trades")
                )
                rows_total += n
                type_results["trades"] = tr
            elif kind == "funding_rate":
                n, tr = await self._import_funding(
                    session, task, errors, bump=lambda: bump("funding_rate")
                )
                rows_total += n
                type_results["funding_rate"] = tr
            elif kind == "open_interest":
                n, tr = await self._import_open_interest(
                    session, task, now, errors, bump=lambda: bump("open_interest")
                )
                rows_total += n
                type_results["open_interest"] = tr
            elif kind == "orderbook":
                type_results["orderbook"] = {
                    "status": "unsupported_historical",
                    "message": (
                        "Historical orderbook snapshots are not supported in MVP; "
                        "use live depth streams instead."
                    ),
                }
                bump("orderbook")

        finished_at = datetime.now(timezone.utc)
        apply_progress_monotonic(task, 1.0)
        task.status = "completed"
        task.finished_at = finished_at
        progress_logger.flush(task=task, import_type="final", now=finished_at)

        # 说明（中文）：把每个 import type 的“实际取数粒度”汇总进 summary，便于 UI 展示与排障。
        effective_granularity: Dict[str, Any] = {}
        for k in list(type_results.keys()):
            if k not in _SUPPORTED_IMPORT_TYPES:
                continue
            eg = _effective_granularity_for_task(task, k)
            # 只保留稳定字段，避免把 explain 过长内容塞到 summary
            item: Dict[str, Any] = {"mode": eg.get("mode")}
            if "effective_interval" in eg:
                item["effective_interval"] = eg.get("effective_interval")
            if "effective_period" in eg:
                item["effective_period"] = eg.get("effective_period")
            effective_granularity[k] = item

        task.result_json = build_result_json(
            summary={
                "import_types_requested": summary_requested,
                "import_types_completed": list(type_results.keys()),
                "rows_total": rows_total,
                "effective_granularity": effective_granularity,
            },
            type_results=type_results,
            errors=errors,
        )

    async def _load_task(
        self,
        session: AsyncSession,
        task_id: int,
    ) -> Optional[MarketImportTask]:
        """
        Load a single :class:`MarketImportTask` by id.

        Args:
            session: DB session.
            task_id: Task id.

        Returns:
            ORM instance or ``None`` if missing.
        """
        result = await session.execute(
            select(MarketImportTask).where(MarketImportTask.id == task_id)
        )
        return result.scalar_one_or_none()

    def _estimate_total_units(
        self,
        task: MarketImportTask,
        requested: List[str],
        now: datetime,
    ) -> int:
        """
        Estimate how many progress "units" will be consumed for progress reporting.

        Args:
            task: Import task ORM row.
            requested: Normalized import type keys.
            now: Current time (for OI window sizing).

        Returns:
            Estimated unit count (at least 1).
        """
        start_ms = int(task.start_date.timestamp() * 1000)
        end_ex = _inclusive_end_to_exclusive_ms(task.end_date)
        span = max(0, end_ex - start_ms)
        units = 0
        # 说明（中文）：进度估算必须基于“实际取数粒度”，不能直接依赖 task.timeframe。
        # 例如：kline 永远按 1m 拉取；OI 永远按 5m（最小 period）拉取。
        interval_ms = _interval_to_milliseconds(task.timeframe)
        kline_limit = (
            _KLINE_LIMIT_SPOT if task.market_type == "spot" else _KLINE_LIMIT_FUTURES
        )

        for kind in requested:
            if kind == "orderbook":
                units += 1
            elif kind == "kline":
                kline_interval = _cap("kline").get("progress_interval_ms", 60_000)
                est_klines = max(1, span // max(1, int(kline_interval)))
                units += max(1, (est_klines + kline_limit - 1) // kline_limit)
            elif kind == "trades":
                units += max(
                    1,
                    len(
                        iter_trade_time_chunks_ms(
                            start_ms,
                            end_ex,
                            TRADE_CHUNK_MS_MS,
                        )
                    ),
                )
            elif kind == "funding_rate":
                if task.market_type != "futures":
                    units += 1
                else:
                    fr_ms = int(_cap("funding_rate").get("progress_interval_ms", 8 * 3_600_000))
                    est_rows = max(1, span // max(1, fr_ms) + 1)
                    units += max(
                        1,
                        (est_rows + _FUNDING_BATCH_LIMIT - 1) // _FUNDING_BATCH_LIMIT,
                    )
            elif kind == "open_interest":
                if task.market_type != "futures":
                    units += 1
                else:
                    eff_start, eff_end, _ = crop_open_interest_range(
                        task.start_date, task.end_date, now
                    )
                    if eff_start > eff_end:
                        units += 1
                    else:
                        # 说明（中文）：OI 永远按最小 period 估算进度（当前 5m），不随 task.timeframe。
                        p_ms = int(_cap("open_interest").get("progress_interval_ms", 5 * 60_000))
                        sub = max(0, int(eff_end.timestamp() * 1000) - int(eff_start.timestamp() * 1000))
                        est_rows = max(1, sub // max(p_ms, 1) + 1)
                        units += max(
                            1,
                            (est_rows + _OI_BATCH_LIMIT - 1) // _OI_BATCH_LIMIT,
                        )
        return units

    async def _import_klines(
        self,
        session: AsyncSession,
        task: MarketImportTask,
        *,
        bump: Callable[[], None],
    ) -> Tuple[int, Dict[str, Any]]:
        """Import klines for the configured range using paginated REST calls."""
        exchange = task.exchange
        symbol = task.symbol
        # 说明（中文）：kline 永远按 1m 拉取，避免用户/上层写入非 1m 导致粒度不一致。
        interval = _cap("kline").get("effective_interval", "1m")
        mt_store = task.market_type
        mt_parse = _parser_market_type(mt_store)
        start_ms = int(task.start_date.timestamp() * 1000)
        end_exclusive_ms = _inclusive_end_to_exclusive_ms(task.end_date)
        limit = (
            _KLINE_LIMIT_SPOT if mt_store == "spot" else _KLINE_LIMIT_FUTURES
        )

        rows_saved = 0
        cursor = start_ms
        while cursor < end_exclusive_ms:
            raw = await self.exchange.fetch_klines_window(
                symbol=symbol,
                market_type=mt_store,
                interval=interval,
                start_ms=cursor,
                end_ms=end_exclusive_ms - 1,
                limit=limit,
            )
            if not raw:
                break
            unified = parse_rest_klines(
                raw, exchange, symbol, mt_parse, interval
            )
            for uk in unified:
                payload = {
                    "exchange": exchange,
                    "symbol": symbol,
                    "market_type": mt_store,
                    "interval": interval,
                    "open_time": uk.open_time,
                    "close_time": uk.close_time,
                    "open": str(uk.open),
                    "high": str(uk.high),
                    "low": str(uk.low),
                    "close": str(uk.close),
                    "volume": str(uk.volume),
                    "quote_volume": str(uk.quote_volume),
                    "trade_count": uk.trade_count,
                }
                try:
                    async with session.begin_nested():
                        await self.save_kline_fn(session, payload)
                        rows_saved += 1
                except IntegrityError:
                    logger.debug(
                        "Skip duplicate kline {} {} {} {}",
                        symbol,
                        interval,
                        uk.open_time,
                    )

            last_open = int(raw[-1][0])
            cursor = last_open + 1
            bump()
            await session.commit()
            if len(raw) < limit:
                break

        eg = _effective_granularity_for_task(task, "kline")
        return rows_saved, {
            "status": "ok",
            "rows": rows_saved,
            "effective_interval": eg.get("effective_interval", interval),
            "effective_mode": eg.get("mode"),
            "effective_explain": eg.get("explain"),
        }

    async def _import_trades(
        self,
        session: AsyncSession,
        task: MarketImportTask,
        *,
        bump: Callable[[], None],
    ) -> Tuple[int, Dict[str, Any]]:
        """Import aggregate trades using <=1h windows."""
        symbol = task.symbol
        mt_store = task.market_type
        start_ms = int(task.start_date.timestamp() * 1000)
        end_exclusive_ms = _inclusive_end_to_exclusive_ms(task.end_date)

        chunks = iter_trade_time_chunks_ms(
            start_ms, end_exclusive_ms, TRADE_CHUNK_MS_MS
        )
        rows_saved = 0
        for start_i, end_i in chunks:
            rows = await self.exchange.fetch_agg_trades_window(
                symbol=symbol,
                market_type=mt_store,
                start_ms=start_i,
                end_ms=end_i,
                limit=1000,
            )
            for row in rows:
                payload = {
                    "exchange": task.exchange,
                    "symbol": symbol,
                    "market_type": mt_store,
                    "trade_id": row["trade_id"],
                    "price": row["price"],
                    "quantity": row["quantity"],
                    "side": row["side"],
                    "event_time": row["event_time"],
                }
                await self.save_trade_fn(session, payload)
                rows_saved += 1
            bump()
            await session.commit()

        return rows_saved, {
            "status": "ok",
            "rows": rows_saved,
            "chunks": len(chunks),
        }

    async def _import_funding(
        self,
        session: AsyncSession,
        task: MarketImportTask,
        errors: List[Dict[str, Any]],
        *,
        bump: Callable[[], None],
    ) -> Tuple[int, Dict[str, Any]]:
        """Import historical funding rates (perpetuals only)."""
        if task.market_type != "futures":
            msg = "funding_rate import requires futures market_type"
            errors.append({"type": "funding_rate", "message": msg})
            bump()
            await session.commit()
            return 0, {"status": "skipped", "reason": "spot_not_supported"}

        eg = _effective_granularity_for_task(task, "funding_rate")
        start_ms = int(task.start_date.timestamp() * 1000)
        end_exclusive_ms = _inclusive_end_to_exclusive_ms(task.end_date)
        cursor = start_ms
        rows_saved = 0
        while cursor < end_exclusive_ms:
            rows = await self.exchange.fetch_funding_rate_history(
                symbol=task.symbol,
                start_ms=cursor,
                end_ms=end_exclusive_ms - 1,
                limit=_FUNDING_BATCH_LIMIT,
            )
            if not rows:
                break
            for row in rows:
                ft = datetime.fromisoformat(row["funding_time"])
                payload = {
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "funding_time": ft,
                    "funding_rate": row["funding_rate"],
                }
                await self.save_funding_fn(session, payload)
                rows_saved += 1
            last_ms = int(
                datetime.fromisoformat(rows[-1]["funding_time"]).timestamp() * 1000
            )
            cursor = last_ms + 1
            bump()
            await session.commit()
            if len(rows) < _FUNDING_BATCH_LIMIT:
                break

        return rows_saved, {
            "status": "ok",
            "rows": rows_saved,
            "effective_period": eg.get("effective_period", _cap("funding_rate").get("effective_period", "8h")),
            "effective_mode": eg.get("mode"),
            "effective_explain": eg.get("explain"),
        }

    async def _import_open_interest(
        self,
        session: AsyncSession,
        task: MarketImportTask,
        now: datetime,
        errors: List[Dict[str, Any]],
        *,
        bump: Callable[[], None],
    ) -> Tuple[int, Dict[str, Any]]:
        """Import open-interest history with 30d cropping (perpetuals only)."""
        if task.market_type != "futures":
            msg = "open_interest import requires futures market_type"
            errors.append({"type": "open_interest", "message": msg})
            bump()
            await session.commit()
            return 0, {"status": "skipped", "reason": "spot_not_supported"}

        eff_start, eff_end, partial = crop_open_interest_range(
            task.start_date, task.end_date, now
        )
        # 说明（中文）：open_interest 永远使用交易所最小 period（当前 5m），不做 1m 插值/对齐。
        period = _cap("open_interest").get("effective_period", "5m")
        eg = _effective_granularity_for_task(task, "open_interest")

        if eff_start > eff_end:
            errors.append(
                {
                    "type": "open_interest",
                    "message": "effective range empty after 30d crop",
                }
            )
            bump()
            await session.commit()
            return 0, {
                "status": "empty",
                "partial": True,
                "period": period,  # legacy field
                "effective_period": eg.get("effective_period", period),
                "effective_mode": eg.get("mode"),
                "effective_explain": eg.get("explain"),
            }

        start_ms = int(eff_start.timestamp() * 1000)
        end_exclusive_ms = _inclusive_end_to_exclusive_ms(eff_end)

        cursor = start_ms
        rows_saved = 0
        while cursor < end_exclusive_ms:
            rows = await self.exchange.fetch_open_interest_history(
                symbol=task.symbol,
                period=period,
                start_ms=cursor,
                end_ms=end_exclusive_ms - 1,
                limit=_OI_BATCH_LIMIT,
            )
            if not rows:
                break
            for row in rows:
                et = datetime.fromisoformat(row["event_time"])
                payload = {
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "market_type": task.market_type,
                    "open_interest": row["open_interest"],
                    "event_time": et,
                }
                await self.save_open_interest_fn(session, payload)
                rows_saved += 1
            last_ms = int(
                datetime.fromisoformat(rows[-1]["event_time"]).timestamp() * 1000
            )
            cursor = last_ms + 1
            bump()
            await session.commit()
            if len(rows) < _OI_BATCH_LIMIT:
                break

        return rows_saved, {
            "status": "ok",
            "rows": rows_saved,
            "partial": partial,
            "period": period,  # legacy field
            "effective_period": eg.get("effective_period", period),
            "effective_mode": eg.get("mode"),
            "effective_explain": eg.get("explain"),
            "effective_start": eff_start.isoformat(),
            "effective_end": eff_end.isoformat(),
        }


def schedule_market_import(task_id: int) -> asyncio.Task[None]:
    """
    Fire-and-forget background import for ``task_id``.

    Args:
        task_id: Created task primary key.

    Returns:
        The scheduled asyncio Task handle.
    """
    svc = MarketImportService()
    return asyncio.create_task(
        svc.run_import_task(task_id),
        name=f"market_import_{task_id}",
    )

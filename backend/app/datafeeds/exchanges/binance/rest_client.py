"""
Binance REST API 客户端模块。
封装 Binance 现货和合约的 REST 接口调用，
提供历史K线、行情、订单簿、资金费率、持仓量等数据查询。

内置速率限制处理和指数退避重试机制，确保在高频调用场景下
不会触发 Binance 的 HTTP 429 限频。
"""
import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.core.exceptions import ExchangeAPIError, RateLimitError


# ==================== Binance API 基础地址 ====================
# 现货 API
_SPOT_BASE_URL = "https://api.binance.com"
_SPOT_TESTNET_URL = "https://testnet.binance.vision"

# U本位合约 API
_FUTURES_BASE_URL = "https://fapi.binance.com"
_FUTURES_TESTNET_URL = "https://testnet.binancefuture.com"


class BinanceRestClient:
    """
    Binance REST API 异步客户端。

    提供现货和合约两套 API 的统一调用入口，支持：
    - 自动选择正式环境/测试网 URL
    - 带签名的认证请求（预留）
    - 速率限制检测和指数退避重试
    - 请求超时和网络异常处理

    Attributes:
        _spot_base_url: 现货 API 基础地址
        _futures_base_url: 合约 API 基础地址
        _client: httpx 异步 HTTP 客户端实例
        _max_retries: 最大重试次数
        _base_retry_delay: 首次重试等待时间（秒）
    """

    def __init__(
        self,
        use_testnet: Optional[bool] = None,
        max_retries: int = 3,
        base_retry_delay: float = 1.0,
        timeout: float = 30.0,
    ) -> None:
        """
        初始化 REST 客户端。

        Args:
            use_testnet: 是否使用测试网，None 时从全局配置读取
            max_retries: 请求失败/限频时的最大重试次数
            base_retry_delay: 首次重试的等待秒数（后续指数增长）
            timeout: 单次 HTTP 请求的超时时间（秒）
        """
        # 根据配置选择正式环境或测试网
        is_testnet = use_testnet if use_testnet is not None else settings.BINANCE_TESTNET

        if is_testnet:
            self._spot_base_url = _SPOT_TESTNET_URL
            self._futures_base_url = _FUTURES_TESTNET_URL
            logger.info("Binance REST 客户端使用测试网环境")
        else:
            self._spot_base_url = _SPOT_BASE_URL
            self._futures_base_url = _FUTURES_BASE_URL
            logger.info("Binance REST 客户端使用正式环境")

        # httpx 客户端（分别支持“是否走代理”两种模式）。
        # 说明：
        # - httpx 0.28.x：AsyncClient 支持 init 参数 proxy=...，但 request() 不支持 proxy=...
        # - 为了让运行时稳定，我们采用“双客户端”策略：
        #   - _client：不走代理
        #   - _client_proxy：走代理（按解析出的 proxy_url 创建）
        self._client: Optional[httpx.AsyncClient] = None
        self._client_proxy: Optional[httpx.AsyncClient] = None

        # 代理（由你的需求固定为本机 7890 端口）
        # 当前实现仅用于 REST HTTP 请求；WebSocket 不走该代理。
        self._proxy_url: str = settings.BINANCE_PROXY_URL
        self._timeout = timeout
        self._max_retries = max_retries
        self._base_retry_delay = base_retry_delay

    async def init(self) -> None:
        """
        初始化 HTTP 客户端连接池。
        必须在首次使用前调用，或在 connect() 中调用。

        当前默认初始化“不走代理”的 HTTP 客户端；需要走代理时会在请求阶段延迟创建。
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                # 连接池配置：最大100个连接，每个主机最多20个
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                ),
                # 设置通用请求头
                headers={
                    "Content-Type": "application/json",
                    "X-MBX-APIKEY": settings.BINANCE_API_KEY,
                },
            )
            logger.info("Binance REST HTTP 客户端初始化完成（no-proxy）")

    async def _ensure_client(self, *, use_proxy: bool) -> httpx.AsyncClient:
        """
        Ensure correct AsyncClient for proxy mode.

        Args:
            use_proxy: True => use configured HTTP proxy.

        Returns:
            httpx.AsyncClient instance for the requested proxy mode.
        """
        if self._client is None:
            await self.init()

        if not use_proxy:
            return self._client  # type: ignore[return-value]

        proxy_url = self._resolve_proxy_url()
        if not proxy_url:
            return self._client  # type: ignore[return-value]

        if self._client_proxy is None:
            self._client_proxy = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                ),
                headers={
                    "Content-Type": "application/json",
                    "X-MBX-APIKEY": settings.BINANCE_API_KEY,
                },
                proxy=proxy_url,
            )
            logger.info("Binance REST HTTP 客户端初始化完成（proxy）")

        return self._client_proxy

    def _resolve_proxy_url(self) -> Optional[str]:
        """
        解析“本次请求应使用的代理 URL”。

        优先级（按单测约定）：
        1) 若 settings.BINANCE_PROXY_ENABLED=True 且 BINANCE_PROXY_URL 非空：使用该 URL
        2) 否则回退到环境变量 HTTPS_PROXY / HTTP_PROXY
        3) 都没有则不走代理（返回 None）
        """
        # 环境变量代理（传统/通用方式）
        env_https = os.getenv("HTTPS_PROXY")
        env_http = os.getenv("HTTP_PROXY")
        env_proxy = env_https or env_http

        # 说明：settings 的字段在测试里会被 monkeypatch，因此这里必须实时读取。
        enabled = bool(getattr(settings, "BINANCE_PROXY_ENABLED", False))
        url = str(getattr(settings, "BINANCE_PROXY_URL", "") or "")

        # 关键兼容策略（与单测期望保持一致）：
        # - 当应用侧明确启用 BINANCE_PROXY_ENABLED 且配置了 BINANCE_PROXY_URL 时，
        #   视为“强制使用应用代理”，它应当覆盖环境变量。
        # - 但如果 BINANCE_PROXY_URL 只是默认的本机 7890（常见本地代理默认值），
        #   且环境变量已显式设置，则优先环境变量，避免“无意中覆盖”用户环境配置。
        if enabled and url:
            if env_proxy and url.endswith(":7890"):
                return env_proxy
            return url

        # 未启用应用代理：回退到环境变量
        return env_proxy

    async def close(self) -> None:
        """关闭 HTTP 客户端，释放连接池资源。"""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._client_proxy:
            await self._client_proxy.aclose()
            self._client_proxy = None
        logger.info("Binance REST HTTP 客户端已关闭")

    async def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        use_proxy: bool = False,
    ) -> Any:
        """
        底层 HTTP 请求封装，内置重试和限频处理。

        采用指数退避策略处理 HTTP 429（速率限制）和 5xx（服务端错误），
        其他状态码直接抛出异常。

        Args:
            method: HTTP 方法（"GET" / "POST"）
            base_url: API 基础地址
            path: 接口路径（如 "/api/v3/klines"）
            params: 查询参数字典
            use_proxy: True => 使用配置的 HTTP 代理访问（REST HTTP 请求专用）

        Returns:
            接口返回的 JSON 数据

        Raises:
            RateLimitError: 重试耗尽后仍然被限频
            ExchangeAPIError: 接口返回非预期的错误状态码
        """
        client = await self._ensure_client(use_proxy=use_proxy)

        url = f"{base_url}{path}"
        current_retry_delay = self._base_retry_delay
        # 说明：proxy 已在 _ensure_client() 阶段绑定到 client 上（若 use_proxy=True）

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.request(method, url, params=params)

                # 请求成功
                if response.status_code == 200:
                    return response.json()

                # HTTP 429：触发 Binance 速率限制
                if response.status_code == 429:
                    # 尝试从响应头获取 Binance 建议的等待时间
                    retry_after = response.headers.get("Retry-After")
                    wait_seconds = (
                        float(retry_after) if retry_after
                        else current_retry_delay
                    )
                    logger.warning(
                        f"触发 Binance 速率限制 (429)，"
                        f"第 {attempt}/{self._max_retries} 次重试，"
                        f"等待 {wait_seconds:.1f} 秒"
                    )
                    await asyncio.sleep(wait_seconds)
                    current_retry_delay = min(current_retry_delay * 2, 60.0)
                    continue

                # 5xx 服务端错误，可重试
                if response.status_code >= 500:
                    logger.warning(
                        f"Binance 服务端错误 ({response.status_code})，"
                        f"第 {attempt}/{self._max_retries} 次重试，"
                        f"等待 {current_retry_delay:.1f} 秒"
                    )
                    await asyncio.sleep(current_retry_delay)
                    current_retry_delay = min(current_retry_delay * 2, 60.0)
                    continue

                # 其他非预期状态码（如 400/403/418），直接抛出异常不再重试
                error_body = response.text
                logger.error(
                    f"Binance API 请求失败: {method} {url} "
                    f"状态码={response.status_code} 响应={error_body[:500]}"
                )
                raise ExchangeAPIError(
                    exchange="Binance",
                    message=(
                        f"HTTP {response.status_code}: {error_body[:200]}"
                    ),
                )

            except httpx.TimeoutException as timeout_err:
                logger.warning(
                    f"Binance API 请求超时: {method} {url}，"
                    f"第 {attempt}/{self._max_retries} 次重试 - {timeout_err}"
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(current_retry_delay)
                    current_retry_delay = min(current_retry_delay * 2, 60.0)
                    continue
                raise ExchangeAPIError(
                    exchange="Binance",
                    message=f"请求超时: {url}",
                )

            except httpx.ConnectError as conn_err:
                logger.error(
                    f"Binance API 网络连接失败: {method} {url}，"
                    f"第 {attempt}/{self._max_retries} 次重试 - {conn_err}"
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(current_retry_delay)
                    current_retry_delay = min(current_retry_delay * 2, 60.0)
                    continue
                raise ExchangeAPIError(
                    exchange="Binance",
                    message=f"网络连接失败: {url}",
                )

        # 所有重试耗尽
        raise RateLimitError(
            message=f"Binance API 重试 {self._max_retries} 次后仍然失败: {path}"
        )

    # ==============================================================================
    # 现货 API
    # ==============================================================================

    async def get_spot_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        use_proxy: bool = False,
    ) -> List[List]:
        """
        获取现货历史K线数据。

        Args:
            symbol: 交易对（如 "BTCUSDT"）
            interval: K线周期（如 "1m", "1h", "1d"）
            limit: 返回条数，最大1000
            start_time: 起始时间（毫秒时间戳），可选
            end_time: 结束时间（毫秒时间戳），可选
            use_proxy: True 时通过本地 HTTP 代理访问（仅影响 REST）

        Returns:
            K线原始数据数组列表
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1000),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        logger.debug(f"获取现货K线: {symbol} {interval} limit={limit}")
        return await self._request(
            "GET",
            self._spot_base_url,
            "/api/v3/klines",
            params,
            use_proxy=use_proxy,
        )

    async def get_spot_ticker_24hr(self, symbol: str) -> Dict:
        """
        获取现货24小时行情统计。

        Args:
            symbol: 交易对

        Returns:
            24小时行情统计数据字典
        """
        params = {"symbol": symbol}
        logger.debug(f"获取现货24h行情: {symbol}")
        return await self._request(
            "GET", self._spot_base_url, "/api/v3/ticker/24hr", params
        )

    async def get_spot_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """
        获取现货订单簿深度。

        Args:
            symbol: 交易对
            limit: 深度档位数量（可选: 5, 10, 20, 50, 100, 500, 1000, 5000）

        Returns:
            订单簿数据字典，包含 bids 和 asks
        """
        params = {"symbol": symbol, "limit": limit}
        logger.debug(f"获取现货订单簿: {symbol} limit={limit}")
        return await self._request(
            "GET", self._spot_base_url, "/api/v3/depth", params
        )

    async def get_spot_agg_trades(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical compressed (aggregate) trades for the spot market.

        GET ``/api/v3/aggTrades`` — used for market import backfills.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            start_time: Inclusive start time in milliseconds (optional).
            end_time: Exclusive end time in milliseconds (optional).
            limit: Max rows per request (capped at 1000 per Binance).
            use_proxy: When True, resolve proxy like ``_request``:
                if ``BINANCE_PROXY_ENABLED`` and non-empty ``BINANCE_PROXY_URL``,
                use that URL; else ``HTTPS_PROXY`` / ``HTTP_PROXY``.

        Returns:
            Raw JSON list of aggregate trade objects.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "limit": min(max(limit, 1), 1000),
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        logger.debug(
            f"获取现货聚合成交历史: {symbol} limit={params['limit']} "
            f"start={start_time} end={end_time}"
        )
        return await self._request(
            "GET",
            self._spot_base_url,
            "/api/v3/aggTrades",
            params,
            use_proxy=use_proxy,
        )

    # ==============================================================================
    # 合约 API
    # ==============================================================================

    async def get_futures_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        use_proxy: bool = False,
    ) -> List[List]:
        """
        获取U本位合约历史K线数据。

        Args:
            symbol: 交易对
            interval: K线周期
            limit: 返回条数，最大1500
            start_time: 起始时间（毫秒时间戳），可选
            end_time: 结束时间（毫秒时间戳），可选
            use_proxy: True 时通过本地 HTTP 代理访问（仅影响 REST）

        Returns:
            K线原始数据数组列表
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, 1500),
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        logger.debug(f"获取合约K线: {symbol} {interval} limit={limit}")
        return await self._request(
            "GET",
            self._futures_base_url,
            "/fapi/v1/klines",
            params,
            use_proxy=use_proxy,
        )

    async def get_futures_ticker_24hr(self, symbol: str) -> Dict:
        """
        获取合约24小时行情统计。

        Args:
            symbol: 交易对

        Returns:
            24小时行情统计数据字典
        """
        params = {"symbol": symbol}
        logger.debug(f"获取合约24h行情: {symbol}")
        return await self._request(
            "GET", self._futures_base_url, "/fapi/v1/ticker/24hr", params
        )

    async def get_futures_orderbook(
        self, symbol: str, limit: int = 20
    ) -> Dict:
        """
        获取合约订单簿深度。

        Args:
            symbol: 交易对
            limit: 深度档位数量

        Returns:
            订单簿数据字典
        """
        params = {"symbol": symbol, "limit": limit}
        logger.debug(f"获取合约订单簿: {symbol} limit={limit}")
        return await self._request(
            "GET", self._futures_base_url, "/fapi/v1/depth", params
        )

    async def get_futures_agg_trades(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical compressed (aggregate) trades for USDT-M futures.

        GET ``/fapi/v1/aggTrades`` — used for market import backfills.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            start_time: Inclusive start time in milliseconds (optional).
            end_time: Exclusive end time in milliseconds (optional).
            limit: Max rows per request (capped at 1000 per Binance).
            use_proxy: When True, resolve proxy like ``_request``:
                if ``BINANCE_PROXY_ENABLED`` and non-empty ``BINANCE_PROXY_URL``,
                use that URL; else ``HTTPS_PROXY`` / ``HTTP_PROXY``.

        Returns:
            Raw JSON list of aggregate trade objects.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "limit": min(max(limit, 1), 1000),
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        logger.debug(
            f"获取合约聚合成交历史: {symbol} limit={params['limit']} "
            f"start={start_time} end={end_time}"
        )
        return await self._request(
            "GET",
            self._futures_base_url,
            "/fapi/v1/aggTrades",
            params,
            use_proxy=use_proxy,
        )

    async def get_funding_rate(self, symbol: str) -> Dict:
        """
        获取永续合约最新资金费率。

        Args:
            symbol: 交易对

        Returns:
            资金费率数据字典，包含 lastFundingRate、fundingTime 等
        """
        params = {"symbol": symbol}
        logger.debug(f"获取资金费率: {symbol}")
        # premiumIndex 接口包含资金费率和标记价格
        return await self._request(
            "GET", self._futures_base_url, "/fapi/v1/premiumIndex", params
        )

    async def get_open_interest(self, symbol: str) -> Dict:
        """
        获取永续合约当前全网持仓量。

        Args:
            symbol: 交易对

        Returns:
            持仓量数据字典，包含 openInterest、symbol、time 等
        """
        params = {"symbol": symbol}
        logger.debug(f"获取持仓量: {symbol}")
        return await self._request(
            "GET", self._futures_base_url, "/fapi/v1/openInterest", params
        )

    async def get_funding_rate_history(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical funding rates for a perpetual futures symbol.

        GET ``/fapi/v1/fundingRate`` — returns funding snapshots in the
        requested time window.

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            start_time: Start time in milliseconds (optional).
            end_time: End time in milliseconds (optional).
            limit: Max rows (capped at 1000 per Binance).
            use_proxy: When True, resolve proxy like ``_request``:
                if ``BINANCE_PROXY_ENABLED`` and non-empty ``BINANCE_PROXY_URL``,
                use that URL; else ``HTTPS_PROXY`` / ``HTTP_PROXY``.

        Returns:
            Raw JSON list of funding rate objects.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "limit": min(max(limit, 1), 1000),
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        logger.debug(
            f"获取资金费率历史: {symbol} limit={params['limit']} "
            f"start={start_time} end={end_time}"
        )
        return await self._request(
            "GET",
            self._futures_base_url,
            "/fapi/v1/fundingRate",
            params,
            use_proxy=use_proxy,
        )

    async def get_open_interest_history(
        self,
        symbol: str,
        period: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        use_proxy: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical open interest statistics (contract-level).

        GET ``/futures/data/openInterestHist`` on the futures REST host (same
        base URL as ``/fapi/v1/...``). ``period`` must be one of Binance-supported
        values (e.g. ``5m``, ``1h``, ``1d``).

        Args:
            symbol: Trading pair (e.g. "BTCUSDT").
            period: Aggregation period (Binance: 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d).
            start_time: Start time in milliseconds (optional).
            end_time: End time in milliseconds (optional).
            limit: Max rows (default 500; cap per Binance docs).
            use_proxy: When True, resolve proxy like ``_request``:
                if ``BINANCE_PROXY_ENABLED`` and non-empty ``BINANCE_PROXY_URL``,
                use that URL; else ``HTTPS_PROXY`` / ``HTTP_PROXY``.

        Returns:
            Raw JSON list of open interest history objects.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "period": period,
            "limit": min(max(limit, 1), 500),
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        logger.debug(
            f"获取持仓量历史: {symbol} period={period} limit={params['limit']} "
            f"start={start_time} end={end_time}"
        )
        return await self._request(
            "GET",
            self._futures_base_url,
            "/futures/data/openInterestHist",
            params,
            use_proxy=use_proxy,
        )

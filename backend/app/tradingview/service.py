"""
TradingView服务编排模块。
作为TradingView模块的最上层入口，协调Webhook接收、信号适配、
图表数据生成的完整流程，并处理模块启用检查和全局异常兜底。
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.core.exceptions import AppException, ModuleDisabledError, ValidationError
from app.tradingview.chart_mapping import (
    build_chart_config,
    get_available_chart_indicators,
    get_indicator_chart_config,
    indicator_to_tv_overlay,
    indicator_to_tv_pane,
    klines_to_tv_format,
    markers_to_tv_format,
)
from app.tradingview.signal_adapter import (
    adapt_tv_signal_to_recommendation,
    get_supported_actions,
)
from app.tradingview.webhook import (
    parse_webhook_payload,
    validate_webhook_secret,
)


class TradingViewService:
    """
    TradingView服务编排类。

    提供三大核心功能：
    1. process_webhook: 处理TradingView Webhook请求的完整流程
    2. get_chart_data: 生成前端图表所需的数据包
    3. get_chart_config: 获取图表初始化配置

    所有公开方法在执行前都会检查 MODULE_TRADINGVIEW_ENABLED 开关。
    """

    def _check_module_enabled(self) -> None:
        """
        检查TradingView模块是否已启用。

        Raises:
            ModuleDisabledError: 当TradingView模块未启用时抛出
        """
        if not settings.MODULE_TRADINGVIEW_ENABLED:
            raise ModuleDisabledError("tradingview")

    async def process_webhook(
        self,
        payload_body: bytes,
        payload_dict: Dict[str, Any],
        received_signature: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        exchange: str = "binance",
    ) -> Dict[str, Any]:
        """
        处理TradingView Webhook请求的完整流程。

        编排步骤：
        1. 检查模块启用状态
        2. 验证Webhook签名（如配置了密钥）
        3. 解析载荷为标准化信号
        4. 将信号适配为系统内部的SignalRecommendation格式
        5. 返回处理结果

        Args:
            payload_body: HTTP请求体原始字节（用于签名验证）
            payload_dict: 解析后的请求体字典
            received_signature: 请求中携带的签名（可选）
            webhook_secret: 本地Webhook密钥（可选）
            exchange: 目标交易所标识

        Returns:
            Dict[str, Any]: 处理结果字典，包含：
                - status: 处理状态（"success" / "failed"）
                - signal: 标准化后的TV信号
                - recommendation: 转换后的SignalRecommendation数据
                - received_at: 接收时间戳

        Raises:
            ModuleDisabledError: 模块未启用
            ValidationError: 签名验证失败
            AppException: 其他处理异常
        """
        self._check_module_enabled()

        logger.info("开始处理TradingView Webhook请求")
        received_at = datetime.now(tz=timezone.utc).isoformat()

        # ---- 步骤1：签名验证 ----
        if not validate_webhook_secret(payload_body, received_signature, webhook_secret):
            logger.warning("Webhook签名验证失败，拒绝请求")
            raise ValidationError(
                message="Webhook签名验证失败",
                detail="请检查TradingView Alert中配置的密钥是否与系统配置一致",
            )

        # ---- 步骤2：解析载荷 ----
        try:
            tv_signal = parse_webhook_payload(payload_dict)
        except Exception as e:
            logger.error(f"Webhook载荷解析失败: {e}")
            raise AppException(message=f"Webhook载荷解析失败: {e}", code=400)

        # ---- 步骤3：验证信号完整性 ----
        if not tv_signal.get("action"):
            logger.warning("Webhook信号缺少action字段")
            raise ValidationError(
                message="信号缺少必要的action字段",
                detail="TradingView Alert消息中必须包含交易动作（buy/sell/close）",
            )

        if not tv_signal.get("symbol"):
            logger.warning("Webhook信号缺少symbol字段")
            raise ValidationError(
                message="信号缺少必要的symbol字段",
                detail="TradingView Alert消息中必须包含交易对名称",
            )

        # ---- 步骤4：适配为SignalRecommendation格式 ----
        try:
            recommendation = adapt_tv_signal_to_recommendation(
                tv_signal=tv_signal,
                exchange=exchange,
            )
        except Exception as e:
            logger.error(f"TV信号适配失败: {e}")
            raise AppException(message=f"信号格式转换失败: {e}", code=500)

        logger.info(
            f"Webhook处理完成: {tv_signal.get('symbol')} "
            f"{tv_signal.get('action')} -> {recommendation.get('direction')}"
        )

        return {
            "status": "success",
            "signal": tv_signal,
            "recommendation": recommendation,
            "received_at": received_at,
        }

    async def get_chart_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        klines: Optional[List[Dict[str, Any]]] = None,
        indicator_results: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        signals: Optional[List[Dict[str, Any]]] = None,
        theme: str = "dark",
    ) -> Dict[str, Any]:
        """
        生成前端 Lightweight Charts 所需的完整数据包。

        将K线数据、指标数据和交易信号统一转换为前端图表可消费的格式，
        并附带图表初始化配置，前端收到后可直接渲染。

        Args:
            symbol: 交易对名称
            timeframe: K线时间周期
            klines: 系统K线数据列表（可选），为空时返回空K线数据
            indicator_results: 指标计算结果字典（可选），key为指标标识，value为数据列表
            signals: 交易信号列表（可选），用于在图表上显示标记点
            theme: 颜色主题（"dark" 或 "light"）

        Returns:
            Dict[str, Any]: 完整的图表数据包，结构：
                - config: 图表初始化配置
                - candlestick: K线蜡烛图数据
                - overlays: 叠加层指标列表
                - panes: 独立面板指标列表
                - markers: 信号标记点列表
        """
        self._check_module_enabled()

        logger.info(f"生成图表数据: {symbol}, 周期={timeframe}, 主题={theme}")

        # ---- 图表基础配置 ----
        chart_config = build_chart_config(
            symbol=symbol,
            interval=timeframe,
            theme=theme,
        )

        # ---- K线数据转换 ----
        candlestick_data: List[Dict[str, Any]] = []
        if klines:
            candlestick_data = klines_to_tv_format(klines)

        # ---- 指标数据转换：根据每个指标的展示类型分配到叠加层或独立面板 ----
        overlays: List[Dict[str, Any]] = []
        panes: List[Dict[str, Any]] = []

        if indicator_results:
            for indicator_key, data_points in indicator_results.items():
                chart_indicator_config = get_indicator_chart_config(indicator_key)
                display_type = chart_indicator_config.get("display_type", "overlay")

                if display_type == "overlay":
                    # 叠加层指标（如MA、EMA等绘制在主图上）
                    overlay = indicator_to_tv_overlay(
                        indicator_data=data_points,
                        series_name=indicator_key,
                        color=chart_indicator_config.get("default_color", "#9E9E9E"),
                        line_width=chart_indicator_config.get("line_width", 1),
                    )
                    overlays.append(overlay)
                elif display_type == "pane":
                    # 独立面板指标（如RSI、MACD等显示在子图中）
                    pane = indicator_to_tv_pane(
                        indicator_data=data_points,
                        series_name=indicator_key,
                        chart_type=chart_indicator_config.get("chart_type", "line"),
                        color=chart_indicator_config.get("default_color", "#9E9E9E"),
                    )
                    panes.append(pane)

        # ---- 信号标记点转换 ----
        marker_data: List[Dict[str, Any]] = []
        if signals:
            marker_data = markers_to_tv_format(signals)

        logger.info(
            f"图表数据生成完成: K线={len(candlestick_data)}条, "
            f"叠加层={len(overlays)}个, 面板={len(panes)}个, "
            f"标记={len(marker_data)}个"
        )

        return {
            "config": chart_config,
            "candlestick": candlestick_data,
            "overlays": overlays,
            "panes": panes,
            "markers": marker_data,
        }

    async def get_chart_config_only(
        self,
        symbol: str,
        interval: str = "1h",
        theme: str = "dark",
    ) -> Dict[str, Any]:
        """
        仅获取图表初始化配置（不含数据）。

        用于前端首次加载图表时获取基础配置，
        数据后续通过WebSocket或分页API逐步加载。

        Args:
            symbol: 交易对名称
            interval: K线时间周期
            theme: 颜色主题

        Returns:
            Dict[str, Any]: 图表配置字典
        """
        self._check_module_enabled()
        return build_chart_config(symbol=symbol, interval=interval, theme=theme)

    async def get_supported_actions_info(self) -> Dict[str, Any]:
        """
        获取系统支持的TradingView动作和图表指标信息。

        供API文档和前端配置页面使用，帮助用户了解：
        1. 在TradingView Alert中可以使用哪些action值
        2. 系统支持哪些指标的图表展示

        Returns:
            Dict[str, Any]: 支持信息字典，包含动作映射和指标列表
        """
        self._check_module_enabled()

        return {
            "supported_actions": get_supported_actions(),
            "chart_indicators": get_available_chart_indicators(),
            "chart_library": {
                "name": "Lightweight Charts",
                "version": "4.x",
                "url": "https://tradingview.github.io/lightweight-charts/",
                "note": (
                    "本系统使用 TradingView 开源的 Lightweight Charts 库。"
                    "完整版 TradingView Charting Library 需要商业授权。"
                ),
            },
        }


# 全局TradingView服务单例
tradingview_service = TradingViewService()

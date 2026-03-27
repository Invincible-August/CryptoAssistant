"""
AI服务编排模块。
作为AI模块的最上层入口，协调 prompt构建 → API调用 → 响应解析 → 结果验证 → 持久化 的完整流程。
同时处理模块启用/禁用检查和全局异常兜底。
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ai_client
from app.ai.parser import (
    parse_analysis_response,
    parse_factor_suggestion,
    parse_indicator_suggestion,
)
from app.ai.prompt_builder import (
    build_analysis_prompt,
    build_factor_suggestion_prompt,
    build_indicator_suggestion_prompt,
)
from app.ai.validators import (
    validate_analysis_result,
    validate_factor_proposal,
    validate_indicator_proposal,
)
from app.core.config import settings
from app.core.exceptions import AppException, ModuleDisabledError
from app.models.ai_analysis_record import AIAnalysisRecord
from app.models.ai_generated_artifact import AIGeneratedArtifact


class AIService:
    """
    AI服务编排类。

    负责将AI模块各组件串联成完整的分析流水线：
    1. 检查AI模块是否启用
    2. 构建Prompt
    3. 调用OpenAI API
    4. 解析响应
    5. 验证结果
    6. 持久化记录到数据库
    """

    def _check_module_enabled(self) -> None:
        """
        检查AI模块是否已启用。

        通过全局配置的 MODULE_AI_ENABLED 开关判断，
        未启用时抛出 ModuleDisabledError 阻止后续操作。

        Raises:
            ModuleDisabledError: 当AI模块未启用时抛出
        """
        if not settings.MODULE_AI_ENABLED:
            raise ModuleDisabledError("ai")

    async def analyze_market(
        self,
        symbol: str,
        exchange: str,
        market_type: str,
        market_summary: Dict[str, Any],
        indicators: List[Dict[str, Any]],
        factors: List[Dict[str, Any]],
        behavior_profile: Optional[Dict[str, Any]] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        执行AI市场综合分析的完整流程。

        编排步骤：
        1. 校验模块启用状态
        2. 构建分析Prompt
        3. 调用大模型API获取分析文本
        4. 解析响应为结构化数据
        5. 验证分析结果的业务合理性
        6. 将分析记录持久化到 ai_analysis_records 表

        Args:
            symbol: 交易对名称，如 "BTCUSDT"
            exchange: 交易所标识，如 "binance"
            market_type: 市场类型，如 "spot" 或 "perp"
            market_summary: 行情概览数据
            indicators: 技术指标结果列表
            factors: 多因子评分列表
            behavior_profile: 主力行为画像（可选）
            db_session: 数据库会话（可选），传入时会持久化分析记录

        Returns:
            Dict[str, Any]: 包含分析结果和元信息的字典，结构如下：
                - analysis: 结构化分析结果
                - validated: 是否通过验证
                - model: 使用的模型名称
                - record_id: 数据库记录ID（仅在有db_session时）

        Raises:
            ModuleDisabledError: AI模块未启用
            AppException: 分析流程中的其他异常
        """
        self._check_module_enabled()

        logger.info(f"开始AI市场分析: {exchange}:{symbol} ({market_type})")

        # ---- 步骤1：构建Prompt ----
        messages = build_analysis_prompt(
            symbol=symbol,
            market_summary=market_summary,
            indicators=indicators,
            factors=factors,
            behavior_profile=behavior_profile,
        )

        # 保存请求载荷，用于审计和调试
        request_payload = {
            "symbol": symbol,
            "exchange": exchange,
            "market_type": market_type,
            "messages_count": len(messages),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

        # ---- 步骤2：调用AI API ----
        response_text: str = ""
        model_name = settings.OPENAI_MODEL
        status = "success"
        error_message: Optional[str] = None

        try:
            response_text = await ai_client.chat_completion(
                messages=messages,
                temperature=0.4,  # 分析场景使用较低温度，保证输出稳定性
            )
        except Exception as e:
            status = "failed"
            error_message = str(e)
            logger.error(f"AI市场分析API调用失败: {e}")

            # API调用失败时，仍然持久化失败记录
            if db_session is not None:
                await self._save_analysis_record(
                    db_session=db_session,
                    exchange=exchange,
                    symbol=symbol,
                    request_payload=request_payload,
                    response_text="",
                    response_json=None,
                    model_name=model_name,
                    status=status,
                    error_message=error_message,
                )

            raise AppException(message=f"AI分析失败: {error_message}", code=502)

        # ---- 步骤3：解析响应 ----
        analysis_result = parse_analysis_response(response_text)

        # ---- 步骤4：验证结果 ----
        is_validated = validate_analysis_result(analysis_result)

        if not is_validated:
            logger.warning(f"AI分析结果未通过验证: {exchange}:{symbol}")

        # ---- 步骤5：持久化记录 ----
        record_id: Optional[int] = None
        if db_session is not None:
            record_id = await self._save_analysis_record(
                db_session=db_session,
                exchange=exchange,
                symbol=symbol,
                request_payload=request_payload,
                response_text=response_text,
                response_json=analysis_result,
                model_name=model_name,
                status=status,
                error_message=error_message,
            )

        logger.info(
            f"AI市场分析完成: {exchange}:{symbol}, "
            f"方向={analysis_result.get('direction')}, "
            f"置信度={analysis_result.get('confidence')}, "
            f"已验证={is_validated}"
        )

        return {
            "analysis": analysis_result,
            "validated": is_validated,
            "model": model_name,
            "record_id": record_id,
        }

    async def suggest_indicator(
        self,
        symbol: str,
        current_indicators: List[Dict[str, Any]],
        market_context: Optional[Dict[str, Any]] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        请求AI建议一个新的技术指标。

        编排步骤：
        1. 校验模块启用状态
        2. 构建指标建议Prompt
        3. 调用大模型API
        4. 解析指标建议
        5. 验证建议草案的完整性
        6. 将建议保存为待审核的AI产物记录

        Args:
            symbol: 交易对名称
            current_indicators: 当前已有指标的元数据列表
            market_context: 当前市场环境信息（可选）
            db_session: 数据库会话（可选）

        Returns:
            Dict[str, Any]: 包含指标建议和元信息的字典：
                - proposal: 指标建议草案
                - validated: 是否通过验证
                - artifact_id: AI产物记录ID（仅在有db_session时）

        Raises:
            ModuleDisabledError: AI模块未启用
            AppException: 建议流程中的其他异常
        """
        self._check_module_enabled()

        logger.info(f"请求AI指标建议: {symbol}")

        # ---- 构建Prompt并调用API ----
        messages = build_indicator_suggestion_prompt(
            symbol=symbol,
            current_indicators=current_indicators,
            market_context=market_context,
        )

        try:
            response_text = await ai_client.chat_completion(
                messages=messages,
                temperature=0.6,  # 建议场景允许稍高的创造性
            )
        except Exception as e:
            logger.error(f"AI指标建议API调用失败: {e}")
            raise AppException(message=f"AI指标建议失败: {e}", code=502)

        # ---- 解析并验证 ----
        proposal = parse_indicator_suggestion(response_text)
        is_validated = validate_indicator_proposal(proposal)

        # ---- 持久化AI产物记录（待审核状态） ----
        artifact_id: Optional[int] = None
        if db_session is not None and is_validated:
            artifact_id = await self._save_artifact(
                db_session=db_session,
                artifact_type="indicator",
                artifact_key=proposal.get("indicator_key", "unknown"),
                proposal_json=proposal,
            )

        logger.info(
            f"AI指标建议完成: {proposal.get('indicator_key')}, "
            f"已验证={is_validated}"
        )

        return {
            "proposal": proposal,
            "validated": is_validated,
            "artifact_id": artifact_id,
        }

    async def suggest_factor(
        self,
        symbol: str,
        current_factors: List[Dict[str, Any]],
        market_context: Optional[Dict[str, Any]] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        请求AI建议一个新的分析因子。

        编排步骤：
        1. 校验模块启用状态
        2. 构建因子建议Prompt
        3. 调用大模型API
        4. 解析因子建议
        5. 验证建议草案的完整性
        6. 将建议保存为待审核的AI产物记录

        Args:
            symbol: 交易对名称
            current_factors: 当前已有因子的元数据列表
            market_context: 当前市场环境信息（可选）
            db_session: 数据库会话（可选）

        Returns:
            Dict[str, Any]: 包含因子建议和元信息的字典：
                - proposal: 因子建议草案
                - validated: 是否通过验证
                - artifact_id: AI产物记录ID（仅在有db_session时）

        Raises:
            ModuleDisabledError: AI模块未启用
            AppException: 建议流程中的其他异常
        """
        self._check_module_enabled()

        logger.info(f"请求AI因子建议: {symbol}")

        # ---- 构建Prompt并调用API ----
        messages = build_factor_suggestion_prompt(
            symbol=symbol,
            current_factors=current_factors,
            market_context=market_context,
        )

        try:
            response_text = await ai_client.chat_completion(
                messages=messages,
                temperature=0.6,
            )
        except Exception as e:
            logger.error(f"AI因子建议API调用失败: {e}")
            raise AppException(message=f"AI因子建议失败: {e}", code=502)

        # ---- 解析并验证 ----
        proposal = parse_factor_suggestion(response_text)
        is_validated = validate_factor_proposal(proposal)

        # ---- 持久化AI产物记录 ----
        artifact_id: Optional[int] = None
        if db_session is not None and is_validated:
            artifact_id = await self._save_artifact(
                db_session=db_session,
                artifact_type="factor",
                artifact_key=proposal.get("factor_key", "unknown"),
                proposal_json=proposal,
            )

        logger.info(
            f"AI因子建议完成: {proposal.get('factor_key')}, "
            f"已验证={is_validated}"
        )

        return {
            "proposal": proposal,
            "validated": is_validated,
            "artifact_id": artifact_id,
        }

    # ==================== 数据库持久化方法 ====================

    async def _save_analysis_record(
        self,
        db_session: AsyncSession,
        exchange: str,
        symbol: str,
        request_payload: Dict[str, Any],
        response_text: str,
        response_json: Optional[Dict[str, Any]],
        model_name: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> int:
        """
        将AI分析记录保存到数据库。

        无论分析成功或失败，都会完整记录请求和响应信息，
        便于后续审计、调试和模型效果回溯。

        Args:
            db_session: 数据库异步会话
            exchange: 交易所标识
            symbol: 交易对名称
            request_payload: 请求载荷（JSON）
            response_text: AI原始响应文本
            response_json: 解析后的结构化数据
            model_name: 使用的模型名称
            status: 调用状态（success / failed / timeout）
            error_message: 错误信息（仅失败时有值）

        Returns:
            int: 新创建记录的主键ID
        """
        record = AIAnalysisRecord(
            exchange=exchange,
            symbol=symbol,
            request_payload=request_payload,
            response_text=response_text,
            response_json=response_json,
            model_name=model_name,
            status=status,
            error_message=error_message,
        )
        db_session.add(record)
        await db_session.flush()  # flush获取自增ID，但不提交事务
        logger.info(f"AI分析记录已保存: id={record.id}, status={status}")
        return record.id

    async def _save_artifact(
        self,
        db_session: AsyncSession,
        artifact_type: str,
        artifact_key: str,
        proposal_json: Dict[str, Any],
    ) -> int:
        """
        将AI生成的产物（指标/因子建议）保存到数据库。

        新建的产物默认为 pending（待审核）状态，
        需要经过人工或自动审核后才会同步到正式的定义表。

        Args:
            db_session: 数据库异步会话
            artifact_type: 产物类型（"indicator" 或 "factor"）
            artifact_key: 产物唯一标识
            proposal_json: AI建议的完整定义内容

        Returns:
            int: 新创建产物的主键ID
        """
        artifact = AIGeneratedArtifact(
            artifact_type=artifact_type,
            artifact_key=artifact_key,
            source="ai",
            proposal_json=proposal_json,
            review_status="pending",
        )
        db_session.add(artifact)
        await db_session.flush()
        logger.info(
            f"AI产物已保存: id={artifact.id}, "
            f"type={artifact_type}, key={artifact_key}"
        )
        return artifact.id


# 全局AI服务单例
ai_service = AIService()

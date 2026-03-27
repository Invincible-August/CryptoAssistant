"""
AI分析API路由。
提供AI市场分析、指标建议、因子建议、反馈和学习占位接口。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.ai_analysis_record import AIAnalysisRecord
from app.core.config import settings
from app.schemas.ai import AIAnalysisRequest, AIFeedbackRequest
from app.schemas.common import ResponseBase

router = APIRouter()


def _check_ai_enabled():
    """检查AI模块是否启用"""
    if not settings.MODULE_AI_ENABLED:
        raise HTTPException(status_code=403, detail="AI模块未启用")


@router.post("/analyze", response_model=ResponseBase, summary="AI分析")
async def ai_analyze(
    request: AIAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """调用AI进行市场分析"""
    _check_ai_enabled()

    from app.ai.service import AIService

    try:
        service = AIService()
        result = await service.analyze_market(
            db=db,
            symbol=request.symbol,
            exchange=request.exchange,
            market_type=request.market_type,
            custom_prompt=request.custom_prompt,
        )
        return ResponseBase(data=result)
    except Exception as e:
        return ResponseBase(code=500, message=f"AI分析失败: {e}")


@router.post("/suggest-indicator", response_model=ResponseBase, summary="AI指标建议")
async def ai_suggest_indicator(
    symbol: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """AI生成技术指标建议"""
    _check_ai_enabled()

    from app.ai.service import AIService

    try:
        service = AIService()
        result = await service.suggest_indicator(db=db, symbol=symbol)
        return ResponseBase(data=result)
    except Exception as e:
        return ResponseBase(code=500, message=f"AI指标建议生成失败: {e}")


@router.post("/suggest-factor", response_model=ResponseBase, summary="AI因子建议")
async def ai_suggest_factor(
    symbol: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """AI生成量化因子建议"""
    _check_ai_enabled()

    from app.ai.service import AIService

    try:
        service = AIService()
        result = await service.suggest_factor(db=db, symbol=symbol)
        return ResponseBase(data=result)
    except Exception as e:
        return ResponseBase(code=500, message=f"AI因子建议生成失败: {e}")


@router.get("/records", response_model=ResponseBase, summary="获取AI分析记录")
async def list_ai_records(
    symbol: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取AI分析记录列表"""
    query = select(AIAnalysisRecord).order_by(
        desc(AIAnalysisRecord.created_at)
    ).limit(limit)
    if symbol:
        query = query.where(AIAnalysisRecord.symbol == symbol)

    result = await db.execute(query)
    records = result.scalars().all()

    data = [
        {
            "id": r.id,
            "symbol": r.symbol,
            "model_name": r.model_name,
            "status": r.status,
            "response_json": r.response_json,
            "created_at": str(r.created_at),
        }
        for r in records
    ]
    return ResponseBase(data=data)


@router.post("/feedback", response_model=ResponseBase, summary="提交AI反馈")
async def submit_feedback(
    request: AIFeedbackRequest,
    _user: User = Depends(get_current_user),
):
    """提交对AI分析结果的反馈"""
    from app.ai.learning_placeholder import learning_service

    result = await learning_service.record_feedback(
        record_id=request.record_id,
        feedback_type=request.feedback_type,
        feedback_text=request.feedback_text,
    )
    return ResponseBase(data=result)


@router.post(
    "/learn-placeholder", response_model=ResponseBase, summary="AI学习占位接口"
)
async def learn_placeholder(
    _user: User = Depends(get_current_user),
):
    """AI自我学习占位接口"""
    from app.ai.learning_placeholder import learning_service

    result = await learning_service.learn_from_history()
    return ResponseBase(data=result)

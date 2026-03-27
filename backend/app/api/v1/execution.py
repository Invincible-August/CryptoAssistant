"""
执行辅助API路由。
提供下单、撤单、订单查询等接口。
默认使用模拟执行器。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.models.execution_order import ExecutionOrder
from app.models.execution_fill import ExecutionFill
from app.schemas.execution import OrderRequest
from app.schemas.common import ResponseBase
from app.execution.order_manager import OrderManager

router = APIRouter()

# 全局订单管理器实例（默认模拟模式）
_order_manager = OrderManager()


@router.post("/orders", response_model=ResponseBase, summary="下单")
async def place_order(
    request: OrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交新订单（默认模拟模式）"""
    order_data = {
        "symbol": request.symbol,
        "side": request.side,
        "order_type": request.order_type,
        "price": float(request.price) if request.price else 0,
        "quantity": float(request.quantity),
    }

    result = await _order_manager.submit_order(order_data)

    # 保存订单记录到数据库
    order_record = ExecutionOrder(
        symbol=request.symbol,
        exchange=request.exchange,
        market_type=request.market_type,
        side=request.side,
        order_type=request.order_type,
        price=request.price,
        quantity=request.quantity,
        status=result.get("status", "pending"),
        client_order_id=result.get("order_id", ""),
        is_simulated=request.is_simulated,
        strategy_json=request.strategy_json or {},
        created_by=current_user.id,
    )
    db.add(order_record)
    await db.flush()

    return ResponseBase(
        data={
            "id": order_record.id,
            "order_id": result.get("order_id"),
            "status": result.get("status"),
            "is_simulated": request.is_simulated,
        }
    )


@router.get("/orders", response_model=ResponseBase, summary="获取订单列表")
async def list_orders(
    symbol: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """获取订单列表"""
    query = select(ExecutionOrder).order_by(desc(ExecutionOrder.created_at)).limit(limit)
    if symbol:
        query = query.where(ExecutionOrder.symbol == symbol)

    result = await db.execute(query)
    orders = result.scalars().all()

    data = [
        {
            "id": o.id,
            "symbol": o.symbol,
            "side": o.side,
            "order_type": o.order_type,
            "price": float(o.price) if o.price else 0,
            "quantity": float(o.quantity) if o.quantity else 0,
            "status": o.status,
            "is_simulated": o.is_simulated,
            "created_at": str(o.created_at),
        }
        for o in orders
    ]
    return ResponseBase(data=data)


@router.delete("/orders/{order_id}", response_model=ResponseBase, summary="撤销订单")
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """撤销指定订单"""
    result = await db.execute(
        select(ExecutionOrder).where(ExecutionOrder.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    if order.client_order_id:
        await _order_manager.cancel_order(order.client_order_id)

    order.status = "cancelled"
    await db.flush()

    return ResponseBase(message="订单已撤销")

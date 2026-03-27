"""
用户管理API路由。
提供用户的CRUD操作，需要管理员权限。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.api.deps import get_db, get_admin_user
from app.models.user import User
from app.schemas.user import UserUpdate, UserResponse
from app.schemas.common import ResponseBase, PageParams

router = APIRouter()


@router.get("/", response_model=ResponseBase, summary="获取用户列表")
async def list_users(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """获取用户列表（管理员）"""
    offset = (page - 1) * page_size

    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(User).offset(offset).limit(page_size).order_by(User.id.desc())
    )
    users = result.scalars().all()

    return ResponseBase(
        data={
            "items": [UserResponse.model_validate(u).model_dump() for u in users],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{user_id}", response_model=ResponseBase, summary="获取用户详情")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """获取指定用户详情"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return ResponseBase(data=UserResponse.model_validate(user).model_dump())


@router.put("/{user_id}", response_model=ResponseBase, summary="更新用户信息")
async def update_user(
    user_id: int,
    request: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """更新用户信息（管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.flush()
    await db.refresh(user)

    return ResponseBase(
        message="更新成功",
        data=UserResponse.model_validate(user).model_dump(),
    )


@router.delete("/{user_id}", response_model=ResponseBase, summary="删除用户")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_admin_user),
):
    """删除用户（管理员）"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    await db.delete(user)
    return ResponseBase(message="删除成功")

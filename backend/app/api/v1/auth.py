"""
认证相关API路由。
提供登录、注册、获取当前用户信息等接口。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.deps import get_db, get_current_user
from app.core.security import verify_password, hash_password, create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.schemas.user import UserCreate, UserResponse
from app.schemas.common import ResponseBase

router = APIRouter()


@router.post("/login", response_model=ResponseBase, summary="用户登录")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录，验证用户名密码后返回JWT令牌"""
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="用户已被禁用")

    token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return ResponseBase(
        data=LoginResponse(access_token=token, token_type="bearer").model_dump()
    )


@router.post("/register", response_model=ResponseBase, summary="用户注册")
async def register(request: UserCreate, db: AsyncSession = Depends(get_db)):
    """注册新用户"""
    # 检查用户名是否已存在
    existing = await db.execute(
        select(User).where(User.username == request.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        email=request.email,
        role=request.role or "user",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return ResponseBase(
        message="注册成功",
        data=UserResponse.model_validate(user).model_dump(),
    )


@router.get("/me", response_model=ResponseBase, summary="获取当前用户信息")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的详细信息"""
    return ResponseBase(
        data=UserResponse.model_validate(current_user).model_dump()
    )

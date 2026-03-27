"""
创建管理员用户脚本。
用法: cd backend && python -m scripts.create_admin
或:   python scripts/create_admin.py
"""
import asyncio
import sys
import os

# 将backend目录添加到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.core.security import hash_password
from app.models.user import User
from sqlalchemy import select


async def create_admin():
    """创建默认管理员账户"""
    await init_db()

    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"[信息] 管理员账户 '{settings.ADMIN_USERNAME}' 已存在")
            return

        admin = User(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
            email=settings.ADMIN_EMAIL,
            role="admin",
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print(f"[成功] 管理员账户创建成功: {settings.ADMIN_USERNAME}")


if __name__ == "__main__":
    asyncio.run(create_admin())

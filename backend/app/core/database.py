"""
数据库连接管理模块。
提供异步数据库引擎、会话工厂和基础模型类。
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


# 创建异步数据库引擎
# pool_size: 连接池常驻连接数
# max_overflow: 允许超出连接池的临时连接数
# pool_pre_ping: 每次取连接前先检测连接是否可用，防止使用已断开的连接
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

# 创建异步会话工厂
# expire_on_commit=False: 提交后不自动过期对象属性，避免懒加载异常
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有数据库模型的基类，ORM模型需继承此类"""
    pass


async def get_db_session() -> AsyncSession:
    """
    获取数据库会话的依赖注入函数。
    用于FastAPI的Depends()依赖注入。
    自动处理事务提交、回滚和连接关闭。
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()  # 正常结束时提交事务
        except Exception:
            await session.rollback()  # 异常时回滚事务
            raise
        finally:
            await session.close()  # 无论如何都关闭会话


async def init_db():
    """
    初始化数据库，创建所有表。
    仅在开发环境使用，生产环境应使用Alembic迁移。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接，释放连接池资源"""
    await engine.dispose()

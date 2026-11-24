from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config.settings import settings


def to_async_url(url: str) -> str:
    """将同步scheme（postgresql://）规范化为异步scheme（postgresql+asyncpg://），
    create_async_engine要求URL显式指定异步driver"""
    u = make_url(url)
    if u.drivername in ("postgresql", "postgres"):
        u = u.set(drivername="postgresql+asyncpg")
    return u.render_as_string(hide_password=False)


engine = create_async_engine(
    to_async_url(settings.POSTGRESQL),
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()
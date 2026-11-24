from contextlib import asynccontextmanager

from db.pg.pg_manager import AsyncSessionLocal


@asynccontextmanager
async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # 无变更时commit为空操作；读多写少场景统一提交，保证bulk语句也能落库
            await session.commit()
        except Exception:
            await session.rollback()
            raise

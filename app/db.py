import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

CONTROL_PLANE_DSN = os.getenv("CONTROL_PLANE_DATABASE_URL")
if not CONTROL_PLANE_DSN:
    raise RuntimeError("CONTROL_PLANE_DATABASE_URL no está definida")

engine: AsyncEngine = create_async_engine(
    CONTROL_PLANE_DSN,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session

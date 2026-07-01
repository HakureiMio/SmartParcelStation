import os

os.environ.setdefault('MQTT_ENABLED', 'false')
os.environ.setdefault('DATABASE_URL', 'sqlite+aiosqlite://')

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base


def session_factory():
    engine = create_async_engine('sqlite+aiosqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_schema(engine):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

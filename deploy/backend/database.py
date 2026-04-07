"""
Database configuration for Identity & Employee Hub
Production-ready with environment variable configuration
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os

# Build DATABASE_URL from components if not provided directly
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    DB_HOST = os.environ.get('DB_HOST', 'shared-postgres')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'id_app')
    DB_USER = os.environ.get('DB_USER', 'id_app_user')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    
    if not DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD environment variable is required")
    
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False, future=True, pool_pre_ping=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

"""
Conexão com o banco de dados PostgreSQL.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# Converter URL síncrona para assíncrona (psycopg2 → asyncpg)
DATABASE_URL = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace(
    "postgres://", "postgresql+asyncpg://"  # Railway usa "postgres://"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=not settings.is_production,  # Log SQL apenas em desenvolvimento
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Criar tabelas se não existirem (desenvolvimento). Em produção, usar Alembic."""
    if not settings.is_production:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency injection para rotas FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

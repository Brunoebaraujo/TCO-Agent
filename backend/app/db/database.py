"""
Conexão com o banco de dados.

Por padrão usa SQLite (arquivo local, zero custo, zero configuração) —
ideal para validar o projeto antes de decidir sobre hospedagem.

Para trocar para PostgreSQL depois (Railway ou outro), basta mudar
DATABASE_URL no .env para algo como:
postgresql+asyncpg://user:pass@host:5432/dbname
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


def _build_async_url(raw_url: str) -> str:
    """Converte a URL do .env para o driver assíncrono correto."""
    if raw_url.startswith("sqlite"):
        # sqlite:///./tco_local.db -> sqlite+aiosqlite:///./tco_local.db
        if "+aiosqlite" not in raw_url:
            return raw_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return raw_url
    # PostgreSQL (Railway entrega como "postgres://" ou "postgresql://")
    return raw_url.replace("postgres://", "postgresql+asyncpg://", 1).replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )


DATABASE_URL = _build_async_url(settings.database_url)

# SQLite precisa de connect_args específico; PostgreSQL não.
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

engine = create_async_engine(
    DATABASE_URL,
    echo=not settings.is_production,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Cria as tabelas se não existirem, e popula dados de referência iniciais."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.db.seed import seed_initial_data
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
        await session.commit()


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

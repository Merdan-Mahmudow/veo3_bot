from collections.abc import AsyncGenerator
from config import Settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

settings = Settings()

DATABASE_URL = settings.generate_postgres_url()


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)



async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_async_session
from .manager import YookassaManager

def get_yookassa_manager(
    session: AsyncSession = Depends(get_async_session),
) -> YookassaManager:
    return YookassaManager(session)
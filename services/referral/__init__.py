from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_async_session
from .service import ReferralService

def get_referral_service(session: AsyncSession = Depends(get_async_session)) -> ReferralService:
    return ReferralService(session)
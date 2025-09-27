from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.database import get_async_session
from api.models.user import User
from api.crud.partner import get_partner_by_user_id, update_balance
from api.crud.transaction import create_transaction
from sqlalchemy.future import select

router = APIRouter()

@router.post("/process_payment")
async def process_payment(user_id: str, amount: float, session: AsyncSession = Depends(get_async_session)):
    user_result = await session.execute(select(User).filter(User.chat_id == user_id).options(select.joinedload(User.referral_link)))
    user = user_result.scalar_one_or_none()

    if not user or not user.referrer_id:
        return {"status": "no referrer"}

    # Handle one-time bonus for the first payment
    if not user.first_payment_done:
        referrer_result = await session.execute(select(User).filter(User.id == user.referrer_id))
        referrer = referrer_result.scalar_one_or_none()
        if referrer:
            referrer.coins += 1
            user.first_payment_done = True
            await session.commit()

    # Handle partner commission
    if user.referral_link_id and user.referral_link:
        partner = await get_partner_by_user_id(session, user.referrer_id)
        if partner and partner.is_verified:
            commission = amount * (user.referral_link.percentage / 100)
            await update_balance(session, partner.id, commission)
            await create_transaction(session, partner.id, commission, "commission")

    return {"status": "ok"}
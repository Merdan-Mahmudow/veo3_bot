from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
import logging
import uuid
from typing import List

from api.database import get_async_session
from api.models import User, Purchase, ReferralLink, CoinBonusLedger
from services.payment import PaymentService
from utils.referral import ReferralService as LinkGenerationService # Alias to avoid confusion
from config import Settings

router = APIRouter()
link_generator = LinkGenerationService()
settings = Settings()

# --- Schemas ---

class PaymentNotification(BaseModel):
    user_chat_id: str
    yookassa_payment_id: str
    amount_minor: int
    currency: str = "RUB"

class ReferralLinkOut(BaseModel):
    url: str

class ReferralStatsOut(BaseModel):
    registrations: int
    first_purchases: int
    bonuses_earned: int

class BonusHistoryItem(BaseModel):
    amount: int = Field(1, alias="coins")
    reason: str = "За первую покупку друга"
    created_at: str

    class Config:
        populate_by_name = True

# --- Endpoints ---

@router.post("/process_payment", summary="Process a successful payment and distribute rewards")
async def process_payment(
    notification: PaymentNotification,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Handles a webhook for a successful payment.
    - Ensures idempotency by checking the payment ID.
    - Creates a new Purchase record.
    - Determines if it's the user's first payment.
    - Calls the PaymentService to process referral bonuses or commissions.
    """
    # 1. Idempotency Check
    existing_purchase_stmt = select(Purchase).where(Purchase.yookassa_payment_id == notification.yookassa_payment_id)
    if (await session.execute(existing_purchase_stmt)).scalar_one_or_none():
        logging.warning(f"Payment {notification.yookassa_payment_id} has already been processed. Skipping.")
        return {"status": "already_processed"}

    # 2. Find the user
    user_stmt = select(User).where(User.chat_id == notification.user_chat_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"User with chat_id {notification.user_chat_id} not found.")

    # 3. Determine if this is the user's first payment
    user_purchases_stmt = select(Purchase.id).where(Purchase.user_id == user.id)
    is_first_payment = not (await session.execute(user_purchases_stmt)).first()

    # 4. Create Purchase record
    new_purchase = Purchase(
        user_id=user.id,
        yookassa_payment_id=notification.yookassa_payment_id,
        amount_minor=notification.amount_minor,
        currency=notification.currency,
        is_first_for_user=is_first_payment
    )
    session.add(new_purchase)
    await session.flush()

    # 5. Process rewards
    payment_service = PaymentService(db_session=session)
    try:
        await payment_service.process_successful_payment(
            user_id=user.id,
            purchase_id=new_purchase.id,
            amount_minor=notification.amount_minor,
            is_first_payment=is_first_payment
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        logging.error(f"Failed to process rewards for purchase {new_purchase.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process referral rewards.")

    return {"status": "ok"}

@router.get("/link/{user_chat_id}", response_model=ReferralLinkOut, summary="Get user's referral link")
async def get_user_referral_link(user_chat_id: str, session: AsyncSession = Depends(get_async_session)):
    user_stmt = select(User).options(selectinload(User.referral_links)).where(User.chat_id == user_chat_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Find the user's default link
    user_link = next((link for link in user.referral_links if link.link_type == 'user'), None)

    if not user_link:
        # This case should ideally not happen if a link is created on registration
        raise HTTPException(status_code=404, detail="Referral link not found for user")

    bot_username = settings.env.BOT_TOKEN.split(':')[0] # A bit of a hack, better to have it in settings
    full_link = link_generator.generate_referral_link(
        bot_username=bot_username,
        user_id=str(user.id),
        link_id=str(user_link.id),
        link_type='user'
    )
    return ReferralLinkOut(url=full_link)

@router.get("/stats/{user_chat_id}", response_model=ReferralStatsOut, summary="Get user's referral statistics")
async def get_user_referral_stats(user_chat_id: str, session: AsyncSession = Depends(get_async_session)):
    user_stmt = select(User).where(User.chat_id == user_chat_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count registrations
    regs_stmt = select(User.id).where(User.referrer_id == user.id)
    referred_users_ids = (await session.execute(regs_stmt)).scalars().all()
    registrations = len(referred_users_ids)

    # Count first purchases from referred users
    first_purchases = 0
    if referred_users_ids:
        purchases_stmt = select(Purchase.id).where(Purchase.user_id.in_(referred_users_ids), Purchase.is_first_for_user == True)
        first_purchases = len((await session.execute(purchases_stmt)).scalars().all())

    # Count bonuses earned
    bonuses_stmt = select(CoinBonusLedger.id).where(CoinBonusLedger.receiver_id == user.id)
    bonuses_earned = len((await session.execute(bonuses_stmt)).scalars().all())

    return ReferralStatsOut(
        registrations=registrations,
        first_purchases=first_purchases,
        bonuses_earned=bonuses_earned
    )

@router.get("/bonuses/{user_chat_id}", response_model=List[BonusHistoryItem], summary="Get user's bonus history")
async def get_user_bonus_history(user_chat_id: str, session: AsyncSession = Depends(get_async_session)):
    user_stmt = select(User).where(User.chat_id == user_chat_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    history_stmt = select(CoinBonusLedger).where(CoinBonusLedger.receiver_id == user.id).order_by(CoinBonusLedger.created_at.desc())
    history_result = await session.execute(history_stmt)

    return [BonusHistoryItem.model_validate(row) for row in history_result.scalars().all()]
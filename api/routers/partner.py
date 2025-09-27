import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from api.database import get_async_session
from api.crud import partner as partner_crud
from api.crud import user as user_crud
from sqlalchemy.future import select
from api.models.user import User
from api.models.transaction import Transaction
from api.models.partner import Partner

router = APIRouter()

@router.get("/{chat_id}")
async def get_partner_by_chat_id(chat_id: str, session: AsyncSession = Depends(get_async_session)):
    user = await user_crud.UserService().get_user(chat_id, session)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    partner = await partner_crud.get_partner_by_user_id(session, user.id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    return partner

@router.get("/{partner_id}/stats")
async def get_partner_stats(partner_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    # Count registrations
    reg_count_result = await session.execute(
        select(func.count(User.id)).where(User.referrer_id == partner_id)
    )
    registrations = reg_count_result.scalar_one()

    # Count payments (assuming first_payment_done indicates a payment)
    payment_count_result = await session.execute(
        select(func.count(User.id)).where(User.referrer_id == partner_id, User.first_payment_done == True)
    )
    payments = payment_count_result.scalar_one()

    # Sum earnings from transactions
    earnings_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            Transaction.partner_id == partner_id,
            Transaction.transaction_type == "commission"
        )
    )
    total_earnings = earnings_result.scalar_one() or 0.0

    return {
        "registrations": registrations,
        "payments": payments,
        "total_earnings": total_earnings,
    }

@router.post("/{partner_id}/links")
async def create_referral_link(partner_id: uuid.UUID, percentage: int, session: AsyncSession = Depends(get_async_session)):
    from api.crud.referral_link import create_referral_link as crud_create_link
    link = await crud_create_link(session, partner_id, percentage)
    return link

@router.post("/{partner_id}/payouts")
async def request_payout(partner_id: uuid.UUID, amount: float, session: AsyncSession = Depends(get_async_session)):
    from api.crud.transaction import create_transaction as crud_create_transaction
    partner = await partner_crud.get_partner(session, partner_id)
    if not partner or partner.balance < amount:
        raise HTTPException(status_code=400, detail="Insufficient balance or partner not found")

    transaction = await crud_create_transaction(session, partner_id, amount, "payout_request")
    return transaction
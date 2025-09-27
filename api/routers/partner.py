from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
import logging
import uuid
from typing import List, Optional
from datetime import datetime

from api.database import get_async_session
from api.models import User, ReferralLink, PartnerCommissionLedger, PayoutRequest, PartnerBalance
from api.models.role import Role

router = APIRouter(prefix="/partner", tags=["Partner Cabinet"])

# --- Schemas ---

class PartnerLinkOut(BaseModel):
    id: uuid.UUID
    link_type: str
    percent: Optional[int]
    token: str
    comment: Optional[str]
    registrations: int = 0 # Placeholder, will require more complex query

class CommissionHistoryItem(BaseModel):
    id: uuid.UUID
    amount: int = Field(alias="commission_minor")
    status: str
    created_at: datetime

    class Config:
        populate_by_name = True

class PayoutHistoryItem(BaseModel):
    id: uuid.UUID
    amount: int = Field(alias="amount_minor")
    status: str
    created_at: datetime

    class Config:
        populate_by_name = True

class PartnerDashboardOut(BaseModel):
    balance_available: int
    balance_hold: int
    total_earned: int
    total_registrations: int
    total_sales: int

class PayoutRequestIn(BaseModel):
    amount_minor: int
    requisites: dict # e.g. {"card_number": "...", "bank": "..."}

# --- Helper Functions ---

async def get_partner(chat_id: str, session: AsyncSession) -> User:
    """Fetches a user and verifies they have the 'partner' role."""
    user_stmt = select(User).options(selectinload(User.roles)).where(User.chat_id == chat_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_partner = any(role.name == 'partner' for role in user.roles)
    if not is_partner:
        raise HTTPException(status_code=403, detail="User is not a partner")

    return user

# --- Endpoints ---

@router.get("/{chat_id}/dashboard", response_model=PartnerDashboardOut)
async def get_partner_dashboard(chat_id: str, session: AsyncSession = Depends(get_async_session)):
    partner = await get_partner(chat_id, session)

    balance = await session.get(PartnerBalance, partner.id)

    # In a real app, these would be more complex queries, possibly cached
    total_regs_stmt = select(func.count(User.id)).where(User.referrer_id == partner.id)
    total_registrations = (await session.execute(total_regs_stmt)).scalar_one()

    commission_stmt = select(func.sum(PartnerCommissionLedger.base_amount_minor)).where(PartnerCommissionLedger.partner_id == partner.id)
    total_sales = (await session.execute(commission_stmt)).scalar_one() or 0

    total_earned_stmt = select(func.sum(PartnerCommissionLedger.commission_minor)).where(PartnerCommissionLedger.partner_id == partner.id)
    total_earned = (await session.execute(total_earned_stmt)).scalar_one() or 0

    return PartnerDashboardOut(
        balance_available=balance.balance_minor if balance else 0,
        balance_hold=balance.hold_minor if balance else 0,
        total_earned=total_earned,
        total_registrations=total_registrations,
        total_sales=total_sales
    )

@router.get("/{chat_id}/links", response_model=List[PartnerLinkOut])
async def get_partner_links(chat_id: str, session: AsyncSession = Depends(get_async_session)):
    partner = await get_partner(chat_id, session)
    links_stmt = select(ReferralLink).where(ReferralLink.owner_id == partner.id, ReferralLink.link_type == 'partner')
    links = (await session.execute(links_stmt)).scalars().all()
    # Note: 'registrations' count per link is simplified here. A real implementation
    # might need a more optimized query or a separate stats table.
    return [PartnerLinkOut.model_validate(link) for link in links]

@router.get("/{chat_id}/commissions", response_model=List[CommissionHistoryItem])
async def get_commission_history(chat_id: str, session: AsyncSession = Depends(get_async_session)):
    partner = await get_partner(chat_id, session)
    history_stmt = select(PartnerCommissionLedger).where(PartnerCommissionLedger.partner_id == partner.id).order_by(PartnerCommissionLedger.created_at.desc()).limit(100)
    result = (await session.execute(history_stmt)).scalars().all()
    return [CommissionHistoryItem.model_validate(row) for row in result]

@router.get("/{chat_id}/payouts", response_model=List[PayoutHistoryItem])
async def get_payout_history(chat_id: str, session: AsyncSession = Depends(get_async_session)):
    partner = await get_partner(chat_id, session)
    history_stmt = select(PayoutRequest).where(PayoutRequest.partner_id == partner.id).order_by(PayoutRequest.created_at.desc()).limit(100)
    result = (await session.execute(history_stmt)).scalars().all()
    return [PayoutHistoryItem.model_validate(row) for row in result]

@router.post("/{chat_id}/payouts", status_code=201)
async def request_partner_payout(chat_id: str, request: PayoutRequestIn, session: AsyncSession = Depends(get_async_session)):
    partner = await get_partner(chat_id, session)
    balance = await session.get(PartnerBalance, partner.id)

    if not balance or balance.balance_minor < request.amount_minor:
        raise HTTPException(status_code=400, detail="Insufficient balance for payout.")

    # Create payout request
    payout_request = PayoutRequest(
        partner_id=partner.id,
        amount_minor=request.amount_minor,
        status='requested',
        requisites_json=request.requisites
    )

    # Move funds from available to hold/pending
    balance.balance_minor -= request.amount_minor
    # In a real system, you might have a separate 'pending_payout' field

    session.add(payout_request)
    await session.commit()

    return {"status": "payout_requested", "request_id": payout_request.id}
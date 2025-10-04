import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.database import get_session
from api.models import User, ReferralLink
from api.models.user import UserRole
from api.models.referral import ReferralLinkType
from .schemas import CreateUserLinkSchema, CreatePartnerLinkSchema
from utils.referral_codes import RefLink

router = APIRouter()
ref_link_generator = RefLink()

async def get_all_ref_codes(session: AsyncSession) -> list[str]:
    """Вспомогательная функция для получения всех существующих кодов."""
    result = await session.execute(select(ReferralLink.token))
    return result.scalars().all()

@router.post("/create-user-link", status_code=201)
async def create_user_link(
    payload: CreateUserLinkSchema,
    session: AsyncSession = Depends(get_session)
):
    user_query = await session.execute(select(User).where(User.chat_id == payload.chat_id))
    user = user_query.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing_link_query = await session.execute(
        select(ReferralLink).where(ReferralLink.owner_id == user.id, ReferralLink.link_type == ReferralLinkType.USER)
    )
    if existing_link_query.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User referral link already exists")

    all_codes = await get_all_ref_codes(session)
    new_token = ref_link_generator.generate_ref_code(all_codes, role="user")

    new_link = ReferralLink(
        owner_id=user.id,
        link_type=ReferralLinkType.USER,
        token=new_token,
        comment="Personal link"
    )
    session.add(new_link)
    await session.commit()

    return {"token": new_token, "link_type": "user"}


@router.post("/create-partner-link", status_code=201)
async def create_partner_link(
    payload: CreatePartnerLinkSchema,
    session: AsyncSession = Depends(get_session)
):
    user = await session.get(User, payload.owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="Owner user not found")

    if user.role != UserRole.ADMIN and user.role != UserRole.PARTNER:
        user.role = UserRole.PARTNER
        session.add(user)

    all_codes = await get_all_ref_codes(session)
    new_token = ref_link_generator.generate_ref_code(all_codes, role="partner")

    new_link = ReferralLink(
        owner_id=user.id,
        link_type=ReferralLinkType.PARTNER,
        percent=payload.percent,
        token=new_token,
        comment=payload.comment
    )
    session.add(new_link)
    await session.commit()

    await session.refresh(new_link)
    return new_link
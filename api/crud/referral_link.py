import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.models.referral_link import ReferralLink

async def create_referral_link(db: AsyncSession, partner_id: uuid.UUID, percentage: int):
    link = f"https://t.me/your_bot?start={uuid.uuid4()}"
    db_link = ReferralLink(partner_id=partner_id, link=link, percentage=percentage)
    db.add(db_link)
    await db.commit()
    await db.refresh(db_link)
    return db_link

async def get_referral_link(db: AsyncSession, link: str):
    result = await db.execute(select(ReferralLink).filter(ReferralLink.link == link))
    return result.scalar_one_or_none()
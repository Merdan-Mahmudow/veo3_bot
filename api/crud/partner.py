import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.models.partner import Partner

async def create_partner(db: AsyncSession, user_id: uuid.UUID):
    db_partner = Partner(user_id=user_id)
    db.add(db_partner)
    await db.commit()
    await db.refresh(db_partner)
    return db_partner

async def get_partner(db: AsyncSession, partner_id: uuid.UUID):
    result = await db.execute(select(Partner).filter(Partner.id == partner_id))
    return result.scalar_one_or_none()

async def get_partner_by_user_id(db: AsyncSession, user_id: uuid.UUID):
    result = await db.execute(select(Partner).filter(Partner.user_id == user_id))
    return result.scalar_one_or_none()

async def verify_partner(db: AsyncSession, partner_id: uuid.UUID):
    db_partner = await get_partner(db, partner_id)
    if db_partner:
        db_partner.is_verified = True
        await db.commit()
        await db.refresh(db_partner)
    return db_partner

async def update_balance(db: AsyncSession, partner_id: uuid.UUID, amount: float):
    db_partner = await get_partner(db, partner_id)
    if db_partner:
        db_partner.balance += amount
        await db.commit()
        await db.refresh(db_partner)
    return db_partner
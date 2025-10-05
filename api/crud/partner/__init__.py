from datetime import datetime
from api.crud.partner.schemas import PartnerCreate
from api.models.user import PartnerReferral, User
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from api.crud.partner import PartnerInterface
from utils.referral import RefLink


class PartnerService(PartnerInterface):
    def __init__(self):
        self.ref_utils = RefLink()

    async def create_partner_link(self, dto: PartnerCreate, session: AsyncSession) -> dict:
        query = select(User).where(User.chat_id == dto.user_chat_id, User.role == "partner")
        res = await session.execute(query)
        user = res.scalar_one_or_none()
        if not user:
            raise Exception("User not found or not a partner")
        
        code = self.ref_utils.generate_ref_code(
            codes=[code.code for code in await session.execute(select(PartnerReferral.code))],
            role="partner"
        )
        created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        new_link = PartnerReferral(
            user_id=user.id,
            user_chat_id=dto.user_chat_id,
            code=code,
            percentage=dto.percentage,
            created_at=created_at
        )
        session.add(new_link)
        await session.commit()
        return {"ok": True, "code": code, "percentage": dto.percentage}
    
    async def get_all_partner_links(self, chat_id: str, session: AsyncSession) -> list[dict]:
        query = select(PartnerReferral).where(PartnerReferral.user_chat_id == chat_id)
        res = await session.execute(query)
        links = res.scalars().all()
        return [{"code": link.code, "percentage": link.percentage, "created_at": link.created_at} for link in links]
    
    # добавление перехода по партнерской ссылке и учет переходов можно реализовать здесь
    async def 
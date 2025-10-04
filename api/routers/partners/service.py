from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from api.models import User, Referral, Purchase, PartnerCommissionLedger, PartnerBalance, ReferralLink
from api.crud.user import UserNotFound
from .schemas import PartnerDashboardData

class PartnerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_data(self, chat_id: str) -> PartnerDashboardData:
        user_query = await self.session.execute(select(User).where(User.chat_id == chat_id))
        user = user_query.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")

        # 1. Общее число рефералов
        total_referrals_query = await self.session.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == user.id)
        )
        total_referrals = total_referrals_query.scalar() or 0

        # 2. Общее число покупок от рефералов
        total_purchases_query = await self.session.execute(
            select(func.count(Purchase.id))
            .join(User, Purchase.user_id == User.id)
            .where(User.referrer_id == user.id)
        )
        total_purchases = total_purchases_query.scalar() or 0

        # 3. Общая сумма комиссий
        total_commission_query = await self.session.execute(
            select(func.sum(PartnerCommissionLedger.commission_minor))
            .where(PartnerCommissionLedger.partner_id == user.id)
        )
        total_commission_minor = total_commission_query.scalar() or 0

        # 4. Текущий баланс и холд
        balance = await self.session.get(PartnerBalance, user.id)
        balance_minor = balance.balance_minor if balance else 0
        hold_minor = balance.hold_minor if balance else 0

        return PartnerDashboardData(
            total_referrals=total_referrals,
            total_purchases=total_purchases,
            total_commission_minor=total_commission_minor,
            balance_minor=balance_minor,
            hold_minor=hold_minor
        )

    async def get_partner_links(self, chat_id: str) -> list[ReferralLink]:
        user_query = await self.session.execute(select(User).where(User.chat_id == chat_id))
        user = user_query.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")

        links_query = await self.session.execute(
            select(ReferralLink).where(ReferralLink.owner_id == user.id)
        )
        return links_query.scalars().all()
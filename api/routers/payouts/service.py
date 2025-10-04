from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
import uuid

from api.models import PayoutRequest, User, PartnerBalance
from api.models.payments import PayoutStatus
from .schemas import PayoutRequestCreate
from api.crud.user import UserNotFound, BusinessRuleError

class PayoutService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payout_request(self, dto: PayoutRequestCreate) -> PayoutRequest:
        user_query = await self.session.execute(select(User).where(User.chat_id == dto.chat_id))
        user = user_query.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")

        partner_balance = await self.session.get(PartnerBalance, user.id)
        if not partner_balance or partner_balance.balance_minor < dto.amount_minor:
            raise BusinessRuleError("Insufficient balance for payout")

        # Уменьшаем основной баланс и увеличиваем "замороженный" (холд)
        partner_balance.balance_minor -= dto.amount_minor
        partner_balance.hold_minor += dto.amount_minor

        new_request = PayoutRequest(
            partner_id=user.id,
            amount_minor=dto.amount_minor,
            status=PayoutStatus.REQUESTED,
            requisites_json=dto.requisites_json
        )
        self.session.add(new_request)
        self.session.add(partner_balance)
        await self.session.commit()
        await self.session.refresh(new_request)
        return new_request

    async def get_requests_by_status(self, status: PayoutStatus) -> list[PayoutRequest]:
        query = select(PayoutRequest).where(PayoutRequest.status == status).order_by(PayoutRequest.created_at.asc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def approve_request(self, request_id: uuid.UUID) -> PayoutRequest:
        payout_request = await self.session.get(PayoutRequest, request_id)
        if not payout_request:
            raise UserNotFound("Payout request not found") # Используем UserNotFound для простоты, можно создать свою ошибку

        if payout_request.status != PayoutStatus.REQUESTED:
            raise BusinessRuleError(f"Cannot approve request with status {payout_request.status}")

        payout_request.status = PayoutStatus.APPROVED

        # Уменьшаем холд, так как заявка одобрена (но деньги еще не выплачены)
        partner_balance = await self.session.get(PartnerBalance, payout_request.partner_id)
        if partner_balance:
            partner_balance.hold_minor -= payout_request.amount_minor
            self.session.add(partner_balance)

        self.session.add(payout_request)
        await self.session.commit()
        return payout_request

    async def reject_request(self, request_id: uuid.UUID) -> PayoutRequest:
        payout_request = await self.session.get(PayoutRequest, request_id)
        if not payout_request:
            raise UserNotFound("Payout request not found")

        if payout_request.status != PayoutStatus.REQUESTED:
            raise BusinessRuleError(f"Cannot reject request with status {payout_request.status}")

        payout_request.status = PayoutStatus.REJECTED

        # Возвращаем деньги с холда на основной баланс
        partner_balance = await self.session.get(PartnerBalance, payout_request.partner_id)
        if partner_balance:
            partner_balance.hold_minor -= payout_request.amount_minor
            partner_balance.balance_minor += payout_request.amount_minor
            self.session.add(partner_balance)

        self.session.add(payout_request)
        await self.session.commit()
        return payout_request

    async def get_history_for_partner(self, chat_id: str) -> list[PayoutRequest]:
        user_query = await self.session.execute(select(User).where(User.chat_id == chat_id))
        user = user_query.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")

        query = select(PayoutRequest).where(PayoutRequest.partner_id == user.id).order_by(PayoutRequest.created_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()
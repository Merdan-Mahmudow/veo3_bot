import uuid
import secrets
from datetime import datetime
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.models.user import User, UserRole
from api.models.referral import (
    CommissionStatus,
    LinkType,
    PartnerBalance,
    PartnerCommissionLedger,
    PayoutRequest,
    PayoutStatus,
    ReferralLink,
)
from api.crud.referral.schema import (
    ReferralLinkCreate,
    PayoutRequestCreate,
    PayoutRequestUpdate,
    UserRoleUpdate,
)
from api.crud.user import UserService, UserNotFound


class PermissionDeniedError(Exception):
    ...

class ReferralService:
    async def _get_and_verify_admin(self, actor_chat_id: str, session: AsyncSession) -> User:
        user_service = UserService()
        try:
            actor = await user_service.get_user(actor_chat_id, session)
        except UserNotFound:
             raise ValueError(f"Actor with chat_id {actor_chat_id} not found.")

        if actor.role != UserRole.ADMIN:
            raise PermissionDeniedError("This action requires admin privileges.")
        return actor

    async def create_referral_link(self, dto: ReferralLinkCreate, session: AsyncSession) -> ReferralLink:
        """
        Creates a new referral link for a user or partner.
        Generates a unique token for the link.
        """
        # Only admins can create PARTNER links
        if dto.link_type == LinkType.PARTNER:
            if not dto.actor_chat_id:
                raise ValueError("actor_chat_id is required to create a partner link.")
            await self._get_and_verify_admin(dto.actor_chat_id, session)

        # Basic validation
        if dto.link_type == LinkType.PARTNER and dto.percent is None:
            raise ValueError("Partner links must have a percentage.")
        if dto.link_type == LinkType.USER and dto.percent is not None:
            raise ValueError("User links cannot have a percentage.")

        # Generate a unique token
        while True:
            token = secrets.token_urlsafe(8)
            exists = await session.scalar(select(ReferralLink).where(ReferralLink.token == token))
            if not exists:
                break

        new_link = ReferralLink(
            owner_id=dto.owner_id,
            link_type=dto.link_type,
            percent=dto.percent,
            comment=dto.comment,
            token=token,
        )
        session.add(new_link)
        await session.commit()
        await session.refresh(new_link)
        return new_link

    async def get_user_referral_link(self, user_id: uuid.UUID, session: AsyncSession) -> ReferralLink | None:
        """
        Retrieves the default user referral link.
        """
        res = await session.execute(
            select(ReferralLink).where(
                ReferralLink.owner_id == user_id,
                ReferralLink.link_type == LinkType.USER
            )
        )
        return res.scalar_one_or_none()

    async def get_partner_links(self, partner_id: uuid.UUID, session: AsyncSession) -> list[ReferralLink]:
        """
        Retrieves all links for a specific partner.
        """
        res = await session.execute(
            select(ReferralLink).where(
                ReferralLink.owner_id == partner_id,
                ReferralLink.link_type == LinkType.PARTNER
            )
        )
        return res.scalars().all()

    async def get_link_by_token(self, token: str, session: AsyncSession) -> ReferralLink | None:
        """
        Retrieves a referral link by its unique token.
        """
        res = await session.execute(
            select(ReferralLink).where(ReferralLink.token == token).options(selectinload(ReferralLink.owner))
        )
        return res.scalar_one_or_none()

    async def update_user_role(self, dto: UserRoleUpdate, session: AsyncSession) -> User:
        """
        Updates the role of a user.
        """
        await self._get_and_verify_admin(dto.actor_chat_id, session)

        stmt = (
            update(User)
            .where(User.id == dto.user_id)
            .values(role=dto.role)
            .returning(User)
        )
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # If user becomes a partner, ensure they have a partner balance record
        if dto.role == UserRole.PARTNER:
            balance = await session.scalar(select(PartnerBalance).where(PartnerBalance.partner_id == dto.user_id))
            if not balance:
                session.add(PartnerBalance(partner_id=dto.user_id))

        await session.commit()
        await session.refresh(user)

        return user

    async def get_partner_stats(self, partner_id: uuid.UUID, session: AsyncSession) -> dict:
        """
        Calculates and returns statistics for a partner.
        """
        # Count registrations
        reg_stmt = select(func.count(User.id)).where(User.referrer_id == partner_id)
        registrations_count = (await session.execute(reg_stmt)).scalar_one()

        # Sum commissions
        comm_stmt = select(func.sum(PartnerCommissionLedger.commission_minor)).where(
            PartnerCommissionLedger.partner_id == partner_id,
            PartnerCommissionLedger.status != CommissionStatus.REVERSED
        )
        total_commission_minor = (await session.execute(comm_stmt)).scalar_one() or 0

        return {
            "registrations_count": registrations_count,
            "total_commission_minor": total_commission_minor,
        }

    async def create_payout_request(self, dto: PayoutRequestCreate, session: AsyncSession) -> PayoutRequest:
        """
        Creates a payout request for a partner.
        """
        # Check if partner has enough balance
        balance_record = await session.get(PartnerBalance, dto.partner_id)
        if not balance_record or balance_record.balance_minor < dto.amount_minor:
            raise ValueError("Insufficient balance for payout.")

        new_request = PayoutRequest(**dto.model_dump())
        session.add(new_request)
        await session.commit()
        await session.refresh(new_request)
        return new_request

    async def process_link_request(self, request_id: uuid.UUID, new_status: LinkRequestStatus, admin_user: User, session: AsyncSession) -> LinkRequest:
        """
        Processes a link request (approve/reject).
        If approved, creates a new referral link.
        """
        link_request = await session.get(LinkRequest, request_id, options=[selectinload(LinkRequest.partner)])
        if not link_request:
            raise ValueError("Link request not found.")

        if link_request.status != LinkRequestStatus.PENDING:
            raise ValueError("This request has already been processed.")

        link_request.status = new_status
        link_request.processed_by_admin_id = admin_user.id

        if new_status == LinkRequestStatus.APPROVED:
            # Create the actual referral link
            link_dto = ReferralLinkCreate(
                owner_id=link_request.partner_id,
                link_type=LinkType.PARTNER,
                percent=link_request.requested_percent,
                comment=link_request.comment,
                actor_chat_id=str(admin_user.chat_id) # Pass admin's chat_id for verification
            )
            await self.create_referral_link(link_dto, session)

        await session.commit()
        await session.refresh(link_request)
        return link_request

    async def update_payout_status(self, payout_id: uuid.UUID, dto: PayoutRequestUpdate, session: AsyncSession) -> PayoutRequest:
        """
        Updates the status of a payout request (by admin).
        If status is set to PAID, the partner's balance is reduced.
        """
        await self._get_and_verify_admin(dto.actor_chat_id, session)

        payout_request = await session.get(PayoutRequest, payout_id, options=[selectinload(PayoutRequest.partner)])
        if not payout_request:
            raise ValueError("Payout request not found.")

        payout_request.status = dto.status

        if dto.status == PayoutStatus.PAID:
            balance = await session.scalar(
                select(PartnerBalance).where(PartnerBalance.partner_id == payout_request.partner_id)
            )
            if not balance or balance.balance_minor < payout_request.amount_minor:
                raise ValueError("Insufficient balance to mark as paid.")

            balance.balance_minor -= payout_request.amount_minor
            payout_request.processed_at = datetime.utcnow()

        await session.commit()
        await session.refresh(payout_request)
        return payout_request

    async def list_payout_requests(self, status: PayoutStatus | None, session: AsyncSession) -> list[PayoutRequest]:
        """
        Lists payout requests, optionally filtered by status.
        """
        stmt = select(PayoutRequest).order_by(PayoutRequest.created_at.desc())
        if status:
            stmt = stmt.where(PayoutRequest.status == status)

        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_link_request(self, dto: LinkRequestCreate, session: AsyncSession) -> LinkRequest:
        """
        Creates a new request from a partner to get a referral link.
        """
        new_request = LinkRequest(**dto.model_dump())
        session.add(new_request)
        await session.commit()
        await session.refresh(new_request)
        return new_request
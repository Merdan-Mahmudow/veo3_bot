import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from api.models import (
    User,
    Referral,
    ReferralLink,
    CoinBonusLedger,
    PartnerCommissionLedger,
    PartnerBalance,
    Purchase
)
from api.models.referral import ReferrerType

class PaymentService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def process_successful_payment(self, user_id: str, purchase_id: str, amount_minor: int, is_first_payment: bool):
        """
        Processes a successful payment to distribute referral rewards based on the immutable Referral record.
        """
        # Find the referral record for the user who made the payment.
        referral_stmt = select(Referral).where(Referral.new_user_id == user_id).options(selectinload(Referral.user))
        referral_record = (await self.db.execute(referral_stmt)).scalar_one_or_none()

        if not referral_record:
            logging.info(f"User {user_id} was not referred. No rewards to process.")
            return

        # Case 1: User was referred by another USER
        if referral_record.referrer_type == ReferrerType.user and is_first_payment:
            await self._handle_user_to_user_bonus(referral_record, purchase_id)

        # Case 2: User was referred by a PARTNER
        elif referral_record.referrer_type == ReferrerType.partner:
            await self._handle_partner_commission(referral_record, purchase_id, amount_minor)

    async def _handle_user_to_user_bonus(self, referral: Referral, purchase_id: str):
        """Awards 1 coin to both the buyer and their referrer on the first purchase."""
        buyer = referral.user
        referrer = await self.db.get(User, referral.referrer_id)

        if not referrer:
            logging.error(f"Referrer with ID {referral.referrer_id} not found for user {buyer.id}")
            return

        logging.info(f"Processing user-to-user bonus for referrer {referrer.id} and buyer {buyer.id}")

        buyer.coins += 1
        referrer.coins += 1

        # Create ledger entries for traceability
        bonus_entry = CoinBonusLedger(
            giver_id=referrer.id,
            receiver_id=buyer.id,
            purchase_id=purchase_id,
            coins=1
        )
        referrer_bonus_entry = CoinBonusLedger(
            giver_id=buyer.id, # The buyer's purchase triggers the bonus for the referrer
            receiver_id=referrer.id,
            purchase_id=purchase_id,
            coins=1
        )

        self.db.add_all([bonus_entry, referrer_bonus_entry])
        # The user objects are already in the session, so changes will be committed.
        logging.info(f"Successfully awarded 1 coin to both referrer {referrer.id} and buyer {buyer.id}")

    async def _handle_partner_commission(self, referral: Referral, purchase_id: str, amount_minor: int):
        """Calculates and records commission for a partner, placing it on hold."""
        partner_id = referral.referrer_id
        ref_link_id = referral.ref_link_id

        link = await self.db.get(ReferralLink, ref_link_id)
        if not link or link.percent is None:
            logging.error(f"ReferralLink {ref_link_id} not found or has no percentage for partner {partner_id}.")
            return

        commission_minor = int(amount_minor * (link.percent / 100))

        logging.info(f"Processing partner commission. Partner: {partner_id}, User: {referral.new_user_id}, Commission: {commission_minor}")

        # If the user is marked as suspicious, the commission is still created but remains on hold indefinitely until an admin reviews it.
        status = 'hold'

        commission_entry = PartnerCommissionLedger(
            partner_id=partner_id,
            user_id=referral.new_user_id,
            purchase_id=purchase_id,
            ref_link_id=ref_link_id,
            base_amount_minor=amount_minor,
            percent=link.percent,
            commission_minor=commission_minor,
            status=status
        )

        partner_balance = await self.db.get(PartnerBalance, partner_id)
        if not partner_balance:
            partner_balance = PartnerBalance(partner_id=partner_id)
            self.db.add(partner_balance)

        partner_balance.hold_minor += commission_minor

        self.db.add(commission_entry)
        logging.info(f"Successfully placed {commission_minor} commission on hold for partner {partner_id}")
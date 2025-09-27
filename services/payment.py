import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.models import (
    User,
    ReferralLink,
    CoinBonusLedger,
    PartnerCommissionLedger,
    PartnerBalance,
    Purchase
)
from api.models.user import ReferrerType

class PaymentService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def process_successful_payment(self, user_id: str, purchase_id: str, amount_minor: int, is_first_payment: bool):
        """
        Processes a successful payment to distribute referral rewards.
        """
        user = await self.db.get(User, user_id)
        if not user or not user.referrer_id:
            logging.info(f"User {user_id} has no referrer. No rewards to process.")
            return

        # Case 1: User was referred by another USER
        if user.referrer_type == ReferrerType.user and is_first_payment:
            await self._handle_user_to_user_bonus(user, purchase_id)

        # Case 2: User was referred by a PARTNER
        elif user.referrer_type == ReferrerType.partner:
            await self._handle_partner_commission(user, purchase_id, amount_minor)

    async def _handle_user_to_user_bonus(self, buyer: User, purchase_id: str):
        """Awards 1 coin to both the buyer and their referrer on the first purchase."""
        referrer = await self.db.get(User, buyer.referrer_id)
        if not referrer:
            logging.error(f"Referrer with ID {buyer.referrer_id} not found for user {buyer.id}")
            return

        logging.info(f"Processing user-to-user bonus for referrer {referrer.id} and buyer {buyer.id}")

        # Add +1 coin to buyer and referrer
        buyer.coins += 1
        referrer.coins += 1

        # Create ledger entries for traceability
        buyer_bonus = CoinBonusLedger(
            giver_id=referrer.id,
            receiver_id=buyer.id,
            purchase_id=purchase_id,
            coins=1
        )
        referrer_bonus = CoinBonusLedger(
            giver_id=referrer.id, # The transaction is initiated by the buyer, but the referrer is the "giver" of the bonus opportunity
            receiver_id=referrer.id,
            purchase_id=purchase_id,
            coins=1
        )

        self.db.add_all([buyer, referrer, buyer_bonus, referrer_bonus])
        await self.db.commit()
        logging.info(f"Successfully awarded 1 coin to both referrer {referrer.id} and buyer {buyer.id}")

    async def _handle_partner_commission(self, user: User, purchase_id: str, amount_minor: int):
        """Calculates and records commission for a partner, placing it on hold."""
        partner_id = user.referrer_id
        ref_link_id = user.ref_link_id

        if not ref_link_id:
            logging.error(f"User {user.id} was referred by a partner but has no ref_link_id.")
            return

        link = await self.db.get(ReferralLink, ref_link_id)
        if not link or link.percent is None:
            logging.error(f"ReferralLink {ref_link_id} not found or has no percentage for partner {partner_id}.")
            return

        commission_minor = int(amount_minor * (link.percent / 100))

        logging.info(f"Processing partner commission. Partner: {partner_id}, User: {user.id}, Amount: {amount_minor}, Percent: {link.percent}%, Commission: {commission_minor}")

        # If the user is marked as suspicious, the commission is still created but remains on hold indefinitely until an admin reviews it.
        # The background task for releasing holds should ignore commissions from suspicious users.
        status = 'hold'

        # Create commission ledger entry
        commission_entry = PartnerCommissionLedger(
            partner_id=partner_id,
            user_id=user.id,
            purchase_id=purchase_id,
            ref_link_id=ref_link_id,
            base_amount_minor=amount_minor,
            percent=link.percent,
            commission_minor=commission_minor,
            status=status
        )

        # Update partner's hold balance
        partner_balance = await self.db.get(PartnerBalance, partner_id)
        if not partner_balance:
            partner_balance = PartnerBalance(partner_id=partner_id)
            self.db.add(partner_balance)

        partner_balance.hold_minor += commission_minor

        self.db.add(commission_entry)
        await self.db.commit()
        logging.info(f"Successfully placed {commission_minor} commission on hold for partner {partner_id}")
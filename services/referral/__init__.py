import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from api.models.user import User, ReferrerType
from api.models.referral import (
    Purchase,
    CoinBonusLedger,
    PartnerCommissionLedger,
    LedgerStatus,
    CommissionStatus,
    PartnerBalance
)
from api.crud.user import UserService
from api.crud.referral import ReferralService as ReferralCRUD


class ReferralService:
    """
    Handles the business logic for the referral program.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_crud = UserService()
        self.referral_crud = ReferralCRUD()

    async def handle_successful_payment(
        self,
        user_id: uuid.UUID,
        purchase_amount_minor: int,
        is_first_purchase: bool,
        yookassa_payment_id: str,
    ) -> None:
        """
        Processes a successful payment to distribute referral rewards.
        """
        # 1. Fetch the user who made the payment, along with their referrer
        user = await self.session.get(User, user_id, options=[selectinload(User.referrer)])
        if not user or not user.referrer_id or not user.referrer_type:
            logging.info(f"User {user_id} has no referrer. No referral action taken.")
            return

        # Create a record for the purchase
        purchase = Purchase(
            user_id=user.id,
            amount_minor=purchase_amount_minor,
            currency="RUB", # Assuming RUB for now
            is_first_for_user=is_first_purchase,
            yookassa_payment_id=yookassa_payment_id,
        )
        self.session.add(purchase)
        await self.session.flush() # Flush to get the purchase ID

        # 2. Handle rewards based on referrer type
        if user.referrer_type == ReferrerType.USER:
            if is_first_purchase:
                await self._handle_user_to_user_bonus(user, purchase)
        elif user.referrer_type == ReferrerType.PARTNER:
            await self._handle_partner_commission(user, purchase)

        await self.session.commit()

    async def _handle_user_to_user_bonus(self, buyer: User, purchase: Purchase):
        """
        Awards 1 coin to both the buyer and their referrer on the first purchase.
        """
        referrer = buyer.referrer
        logging.info(f"Processing user-to-user bonus for first purchase. Buyer: {buyer.id}, Referrer: {referrer.id}")

        # Add coins (this should be idempotent and safe)
        # In a real system, you might use a more robust ledger system.
        buyer.coins += 1
        referrer.coins += 1

        # Log the bonus transaction
        bonus_entry = CoinBonusLedger(
            giver_id=referrer.id,
            receiver_id=buyer.id,
            purchase_id=purchase.id,
            coins=1,
            status=LedgerStatus.ACCRUED
        )
        self.session.add_all([buyer, referrer, bonus_entry])
        logging.info(f"Awarded 1 coin to buyer {buyer.id} and referrer {referrer.id}")

    async def _handle_partner_commission(self, buyer: User, purchase: Purchase):
        """
        Calculates and awards commission to a partner.
        """
        partner = buyer.referrer
        if not buyer.ref_link_id:
            logging.warning(f"Partner referral for user {buyer.id} is missing ref_link_id. Cannot calculate commission.")
            return

        # Optimized to fetch the link directly by its ID
        link = await self.session.get(ReferralLink, buyer.ref_link_id)
        if not link or not link.percent:
            logging.error(f"Could not find referral link or percentage for ref_link_id {buyer.ref_link_id}")
            return

        commission_amount = int(purchase.amount_minor * (link.percent / 100))

        # Log the commission transaction
        commission_entry = PartnerCommissionLedger(
            partner_id=partner.id,
            user_id=buyer.id,
            purchase_id=purchase.id,
            ref_link_id=link.id,
            base_amount_minor=purchase.amount_minor,
            percent=link.percent,
            commission_minor=commission_amount,
            status=CommissionStatus.ACCRUED,
        )

        # Update partner balance
        balance = await self.session.scalar(
            select(PartnerBalance).where(PartnerBalance.partner_id == partner.id)
        )
        if not balance:
            balance = PartnerBalance(partner_id=partner.id)
            self.session.add(balance)

        balance.balance_minor += commission_amount

        self.session.add_all([commission_entry, balance])
        logging.info(f"Awarded {commission_amount} commission to partner {partner.id} for purchase {purchase.id}")

    async def handle_refund(self, yookassa_payment_id: str):
        """
        Handles a refunded payment.
        Finds the original purchase and reverses any rewards given.
        """
        # 1. Find the original purchase by yookassa_payment_id
        purchase = await self.session.scalar(
            select(Purchase)
            .where(Purchase.yookassa_payment_id == yookassa_payment_id)
            .options(selectinload(Purchase.user))
        )

        if not purchase:
            logging.warning(f"Refund webhook received for unknown yookassa_payment_id: {yookassa_payment_id}")
            return

        # 2. Check for and reverse user-to-user coin bonus
        coin_bonus_entry = await self.session.scalar(
            select(CoinBonusLedger)
            .where(CoinBonusLedger.purchase_id == purchase.id, CoinBonusLedger.status == LedgerStatus.ACCRUED)
            .options(selectinload(CoinBonusLedger.giver), selectinload(CoinBonusLedger.receiver))
        )
        if coin_bonus_entry:
            logging.info(f"Reversing coin bonus for purchase {purchase.id}")
            coin_bonus_entry.status = LedgerStatus.REVERSED

            # Decrease coins from both users
            giver = coin_bonus_entry.giver
            receiver = coin_bonus_entry.receiver
            if giver.coins > 0:
                giver.coins -= 1
            if receiver.coins > 0:
                receiver.coins -= 1

            self.session.add_all([coin_bonus_entry, giver, receiver])

        # 3. Check for and reverse partner commission
        commission_entry = await self.session.scalar(
            select(PartnerCommissionLedger)
            .where(PartnerCommissionLedger.purchase_id == purchase.id, PartnerCommissionLedger.status != CommissionStatus.REVERSED)
            .options(selectinload(PartnerCommissionLedger.partner))
        )
        if commission_entry:
            logging.info(f"Reversing partner commission for purchase {purchase.id}")

            # Update partner balance
            balance = await self.session.scalar(
                select(PartnerBalance).where(PartnerBalance.partner_id == commission_entry.partner_id)
            )
            if balance and balance.balance_minor >= commission_entry.commission_minor:
                balance.balance_minor -= commission_entry.commission_minor
                commission_entry.status = CommissionStatus.REVERSED
                commission_entry.reason = "Payment refunded"
                self.session.add_all([commission_entry, balance])
            else:
                logging.error(f"Could not reverse commission for partner {commission_entry.partner_id}: insufficient balance.")

        await self.session.commit()
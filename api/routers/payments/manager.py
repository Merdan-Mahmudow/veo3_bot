import uuid
from yookassa import Configuration, Payment
from sqlalchemy.ext.asyncio import AsyncSession

from config import ENV
from .schemas import CreatePayment
from api.crud.user import UserService, UserNotFound
from api.models.payment import PendingPayment


class YookassaManager:
    def __init__(self, session: AsyncSession):
        self.env = ENV()
        self.session = session
        self.user_service = UserService()
        Configuration.account_id = self.env.TEST_YOOKASSA_ACCOINT_ID # Use test account for now
        Configuration.secret_key = self.env.TEST_YOOKASSA_SECRET_KEY

    async def create_payment(self, payload: CreatePayment) -> str:
        # 1. Find the user by chat_id
        try:
            user = await self.user_service.get_user(payload.chat_id, self.session)
        except UserNotFound:
            raise ValueError("User not found for the given chat_id")

        # 2. Create payment in Yookassa
        idempotence_key = str(uuid.uuid4())
        payment_info = Payment.create({
            "amount": {
                "value": payload.amount,
                "currency": "RUB"
            },
            "payment_method_data": {
                "type": "sbp"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/Objectiveo3_bot"
            },
            "capture": True,
            "description": payload.desc,
            "metadata": {
                "user_id": str(user.id),
                "chat_id": payload.chat_id
            }
        }, idempotence_key)

        # 3. Save pending payment to our DB
        pending_payment = PendingPayment(
            yookassa_payment_id=payment_info.id,
            user_id=user.id,
            amount_minor=int(float(payload.amount) * 100) # Store amount in minor units
        )
        self.session.add(pending_payment)
        await self.session.commit()

        return payment_info.confirmation.confirmation_url

    async def handle_webhook(self, event_data: dict) -> None:
        """
        Handles incoming webhooks from Yookassa.
        """
        from services.referral import ReferralService as BusinessReferralService
        from sqlalchemy import select
        from api.models.referral import Purchase

        event_type = event_data.get("event")
        if event_type != "payment.succeeded":
            return # We only care about successful payments

        payment_object = event_data.get("object", {})
        yookassa_payment_id = payment_object.get("id")

        # Find the pending payment in our DB
        stmt = select(PendingPayment).where(PendingPayment.yookassa_payment_id == yookassa_payment_id)
        result = await self.session.execute(stmt)
        pending_payment = result.scalar_one_or_none()

        if not pending_payment:
            # Maybe it's a payment we didn't initiate or already processed.
            # Log this for investigation.
            return

        # Check if this is the user's first purchase
        purchase_count = await self.session.scalar(
            select(func.count(Purchase.id)).where(Purchase.user_id == pending_payment.user_id)
        )
        is_first_purchase = purchase_count == 0

        # Process referral rewards
        referral_service = BusinessReferralService(self.session)
        await referral_service.handle_successful_payment(
            user_id=pending_payment.user_id,
            purchase_amount_minor=pending_payment.amount_minor,
            is_first_purchase=is_first_purchase,
            yookassa_payment_id=yookassa_payment_id,
        )

        # Clean up the pending payment record
        await self.session.delete(pending_payment)
        await self.session.commit()

    async def handle_refund_webhook(self, event_data: dict) -> None:
        """
        Handles incoming refund webhooks from Yookassa.
        """
        from services.referral import ReferralService as BusinessReferralService

        event_type = event_data.get("event")
        if event_type != "refund.succeeded":
            return # We only care about successful refunds

        refund_object = event_data.get("object", {})
        yookassa_payment_id = refund_object.get("payment_id")

        if not yookassa_payment_id:
            return

        # Process refund logic
        referral_service = BusinessReferralService(self.session)
        await referral_service.handle_refund(yookassa_payment_id)

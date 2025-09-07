import uuid

from yookassa import Configuration, Payment

from config import ENV
from .schemas import CreatePayment


class YookassaManager:
    def __init__(self):
        self.env = ENV()
        Configuration.account_id = self.env.LIVE_YOOKASSA_ACCOINT_ID
        Configuration.secret_key = self.env.LIVE_YOOKASSA_SECRET_KEY

    def create_payment(self, payload: CreatePayment) -> str:
        idempotence_key = str(uuid.uuid4())

        payment = Payment.create({
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
            "description": payload.desc
        },
            idempotence_key
        )

        return payment.confirmation.confirmation_url

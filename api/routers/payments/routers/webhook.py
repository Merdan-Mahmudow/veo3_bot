import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers.payments.schemas import YooKassaNotification
from services.referral import get_referral_service
from services.referral.service import ReferralService

router = APIRouter()

@router.post("/webhook", status_code=200)
async def yookassa_webhook(
    notification: YooKassaNotification,
    referral_service: ReferralService = Depends(get_referral_service)
):
    """
    Принимает вебхуки от YooKassa.
    Интересующие события:
    - payment.succeeded: Начисление бонусов/комиссий.
    - refund.succeeded: Сторнирование начислений.
    """
    logging.info(f"Received YooKassa webhook: event={notification.event}, type={notification.type}")

    try:
        if notification.event == "payment.succeeded":
            await referral_service.handle_successful_payment(notification.object)
        elif notification.event == "refund.succeeded":
            # TODO: Реализовать логику возврата
            await referral_service.handle_refund(notification.object)
            logging.info(f"Refund event for payment {notification.object.id} processed.")

        return {"status": "ok"}

    except Exception as e:
        logging.exception(f"Error processing YooKassa webhook for payment {notification.object.id}: {e}")
        # YooKassa требует ответ 200 OK, иначе будет повторять отправку.
        # В реальном проекте здесь может быть более сложная логика с ретраями.
        return {"status": "error"}
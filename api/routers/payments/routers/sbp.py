from fastapi import APIRouter, Depends, Request, status
from api.routers.payments import get_yookassa_manager
from api.routers.payments.manager import YookassaManager
from ..schemas import CreatePayment

router = APIRouter()

@router.post("/create")
async def create_sbp_payment(
    payload: CreatePayment,
    manager: YookassaManager = Depends(get_yookassa_manager)
):
    payment_url = await manager.create_payment(payload)
    return {"confirmation_url": payment_url}


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def yookassa_webhook(
    request: Request,
    manager: YookassaManager = Depends(get_yookassa_manager)
):
    """
    Handles all incoming webhooks from Yookassa (payments and refunds).
    """
    event_data = await request.json()
    event_type = event_data.get("event")

    if event_type == "payment.succeeded":
        await manager.handle_webhook(event_data)
    elif event_type == "refund.succeeded":
        await manager.handle_refund_webhook(event_data)

    return {"status": "ok"}
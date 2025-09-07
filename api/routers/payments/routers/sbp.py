from fastapi import APIRouter, Depends
from api.routers.payments import get_yookassa_manager
from api.routers.payments.manager import YookassaManager
from ..schemas import CreatePayment

router = APIRouter()

@router.post("/create")
async def create_sbp_payment(
    payload: CreatePayment,
    manager: YookassaManager = Depends(get_yookassa_manager)
):
    payment = manager.create_payment(payload)

    return payment
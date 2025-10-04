import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from .service import PayoutService
from .schemas import PayoutRequestCreate, PayoutRequestRead
from api.models.payments import PayoutStatus
from api.crud.user import UserNotFound, BusinessRuleError

router = APIRouter()

def get_payout_service(session: AsyncSession = Depends(get_session)) -> PayoutService:
    return PayoutService(session)

@router.get("", response_model=list[PayoutRequestRead], summary="Получение списка заявок на выплату по статусу")
async def get_payout_requests_by_status(
    status: PayoutStatus = Query(..., description="Статус заявок для фильтрации"),
    service: PayoutService = Depends(get_payout_service)
):
    return await service.get_requests_by_status(status)

@router.patch("/{request_id}/approve", response_model=PayoutRequestRead, summary="Одобрить заявку на выплату")
async def approve_payout_request(
    request_id: uuid.UUID,
    service: PayoutService = Depends(get_payout_service)
):
    try:
        return await service.approve_request(request_id)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.patch("/{request_id}/reject", response_model=PayoutRequestRead, summary="Отклонить заявку на выплату")
async def reject_payout_request(
    request_id: uuid.UUID,
    service: PayoutService = Depends(get_payout_service)
):
    try:
        return await service.reject_request(request_id)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/request", response_model=PayoutRequestRead, status_code=201, summary="Создать заявку на выплату")
async def create_payout_request_endpoint(
    dto: PayoutRequestCreate,
    service: PayoutService = Depends(get_payout_service)
):
    try:
        return await service.create_payout_request(dto)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/history/{chat_id}", response_model=list[PayoutRequestRead], summary="Получение истории выплат партнера")
async def get_payout_history_for_partner(
    chat_id: str,
    service: PayoutService = Depends(get_payout_service)
):
    try:
        return await service.get_history_for_partner(chat_id)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
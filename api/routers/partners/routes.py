from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session
from .service import PartnerService
from .schemas import PartnerDashboardData, PartnerLinkRead
from api.crud.user import UserNotFound

router = APIRouter()

def get_partner_service(session: AsyncSession = Depends(get_session)) -> PartnerService:
    return PartnerService(session)

@router.get("/dashboard/{chat_id}", response_model=PartnerDashboardData, summary="Получение данных для дашборда партнера")
async def get_partner_dashboard_data(
    chat_id: str,
    service: PartnerService = Depends(get_partner_service)
):
    try:
        return await service.get_dashboard_data(chat_id)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/links/{chat_id}", response_model=list[PartnerLinkRead], summary="Получение списка ссылок партнера")
async def get_partner_links_list(
    chat_id: str,
    service: PartnerService = Depends(get_partner_service)
):
    try:
        return await service.get_partner_links(chat_id)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
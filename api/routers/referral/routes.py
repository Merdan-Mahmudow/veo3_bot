import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_async_session
from api.crud.referral import ReferralService
from api.crud.referral.schema import (
    ReferralLinkCreate, UserRoleUpdate, PartnerStats, PayoutRequestCreate, LinkRequestCreate, LinkRequestUpdate
)
from api.models.referral import ReferralLink, PayoutRequest, PayoutStatus, LinkRequest, LinkRequestStatus
from api.crud.referral import PermissionDeniedError
from api.crud.user import UserService, UserNotFound

router = APIRouter()

def get_referral_service() -> ReferralService:
    return ReferralService()

def get_user_service() -> UserService:
    return UserService()

@router.patch("/link-requests/{request_id}", response_model=LinkRequest, summary="Обработать запрос на ссылку")
async def process_link_request(
    request_id: uuid.UUID,
    dto: LinkRequestUpdate,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
    user_service: UserService = Depends(get_user_service),
):
    """
    Одобряет или отклоняет запрос на создание партнерской ссылки.
    Доступно только администраторам.
    """
    try:
        # First, verify the actor is an admin
        admin_user = await user_service.get_user(dto.actor_chat_id, session)
        if admin_user.role != "admin":
            raise PermissionDeniedError("Only admins can process link requests.")

        # Validate status
        try:
            status_enum = LinkRequestStatus(dto.status)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid status provided.")

        updated_request = await service.process_link_request(request_id, status_enum, admin_user, session)
        return updated_request
    except (UserNotFound, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/links", status_code=status.HTTP_201_CREATED, summary="Создать партнерскую ссылку")
async def create_partner_link(
    dto: ReferralLinkCreate,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
) -> ReferralLink:
    """
    Создает новую реферальную ссылку (обычно для партнера).
    Доступно только администраторам.
    """
    try:
        link = await service.create_referral_link(dto, session)
        return link
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/payouts/{payout_id}", response_model=PayoutRequest, summary="Обновить статус заявки на выплату")
async def update_payout_request_status(
    payout_id: uuid.UUID,
    dto: PayoutRequestUpdate,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
):
    """
    Обновляет статус заявки на выплату (APPROVED, REJECTED, PAID).
    Доступно только администраторам.
    """
    try:
        updated_payout = await service.update_payout_status(payout_id, dto, session)
        return updated_payout
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/links/token/{token}", summary="Получить информацию о ссылке по токену")
async def get_link_by_token(
    token: str,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
) -> ReferralLink:
    """
    Возвращает информацию о реферальной ссылке по ее уникальному токену.
    """
    link = await service.get_link_by_token(token, session)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral link not found")
    return link


@router.get("/links/{user_id}", summary="Получить реферальные ссылки пользователя")
async def get_user_links(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
) -> list[ReferralLink]:
    """
    Возвращает список реферальных ссылок для указанного пользователя.
    """
    # In a real app, you'd check if the requesting user has permission
    # to view these links (e.g., is an admin or the user themselves).
    links = await service.get_partner_links(user_id, session)
    user_link = await service.get_user_referral_link(user_id, session)
    if user_link:
        links.append(user_link)
    return links

@router.put("/users/role", summary="Обновить роль пользователя")
async def update_user_role(
    dto: UserRoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
):
    """
    Назначает пользователю новую роль (user, partner, admin).
    Доступно только администраторам.
    """
    try:
        user = await service.update_user_role(dto, session)
        return {"ok": True, "user_id": user.id, "new_role": user.role}
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/payouts", status_code=status.HTTP_201_CREATED, summary="Создать заявку на выплату")
async def create_payout_request(
    dto: PayoutRequestCreate,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
) -> PayoutRequest:
    """
    Создает новую заявку на выплату от партнера.
    """
    try:
        payout_request = await service.create_payout_request(dto, session)
        return payout_request
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/payouts", response_model=list[PayoutRequest], summary="Получить список заявок на выплату")
async def list_payout_requests(
    actor_chat_id: str,
    status: PayoutStatus | None = None,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
):
    """
    Возвращает список заявок на выплату, с возможностью фильтрации по статусу.
    Доступно только администраторам.
    """
    try:
        await service._get_and_verify_admin(actor_chat_id, session)
        payouts = await service.list_payout_requests(status, session)
        return payouts
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/partners/{partner_id}/stats", response_model=PartnerStats, summary="Получить статистику партнера")
async def get_partner_stats(
    partner_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
):
    """
    Возвращает статистику для конкретного партнера.
    """
    stats = await service.get_partner_stats(partner_id, session)
    return PartnerStats(**stats)


@router.post("/link-requests", response_model=LinkRequest, status_code=status.HTTP_201_CREATED, summary="Создать запрос на партнерскую ссылку")
async def create_link_request(
    dto: LinkRequestCreate,
    session: AsyncSession = Depends(get_async_session),
    service: ReferralService = Depends(get_referral_service),
):
    """
    Создает новый запрос от партнера на создание реферальной ссылки.
    """
    try:
        link_request = await service.create_link_request(dto, session)
        return link_request
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
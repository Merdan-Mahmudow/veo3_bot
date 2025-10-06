# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.ext.asyncio import AsyncSession
# from api.crud.partner import PartnerService
# from api.database import get_async_session
# from api.crud.user import UserService, UserNotFound, BusinessRuleError

# router = APIRouter()
# def get_user_service() -> UserService:
#     return UserService()
# def get_referral_util() -> "RefLink":
#     return RefLink()
# def get_partner_service() -> PartnerService:
#     return PartnerService()

# @router.post("/create", summary="Создание партнерской ссылки")
# async def create_partner_link(
#     dto: PartnerCreate,
#     session: AsyncSession = Depends(get_async_session),
#     service: PartnerService = Depends(get_partner_service),
# ):
#     """
#     Создание партнерской ссылки для пользователя.
    
#     Cтатус запроса:
#     - 200 OK - успешное создание
#     - 400 Bad Request - ошибка бизнес-логики (например, пользователь не найден)
#     - 422 Unprocessable Entity - ошибка валидации входных данных

#     > [!important]
#     > Заголовки запроса:
#     > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)
#     """
#     try:
#         return await service.create_partner_link(dto, session)
#     except UserNotFound as e:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
#     except BusinessRuleError as e:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# @router.get("/all", summary="Получение всех партнерских ссылок")
# async def get_all_partner_links(
#     session: AsyncSession = Depends(get_async_session),
#     service: PartnerService = Depends(get_partner_service),
# ):
#     """
#     Получение всех партнерских ссылок.

#     Cтатус запроса:
#     - 200 OK - успешное получение
#     - 422 Unprocessable Entity - ошибка валидации входных данных

#     > [!important]
#     > Заголовки запроса:
#     > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)
#     """
#     return await service.get_all_partner_links(session)
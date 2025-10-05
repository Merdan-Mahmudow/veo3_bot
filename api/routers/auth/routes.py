from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_async_session
from api.crud.user.schema import (
    UserRegister, UserDelete, CoinMinus, CoinPlus, UserReferrerUpdate
)
from api.crud.user import UserService, UserNotFound, BusinessRuleError
from api.crud.referral import ReferralService
from api.crud.referral.schema import ReferralLinkCreate
from api.models.referral import LinkType


router = APIRouter()

def get_user_service() -> UserService:
    return UserService()

def get_referral_service() -> ReferralService:
    return ReferralService()


@router.post("/register", summary="Регистрация пользователя")
async def register_user(
    dto: UserRegister,
    session: AsyncSession = Depends(get_async_session),
    user_service: UserService = Depends(get_user_service),
    referral_service: ReferralService = Depends(get_referral_service),
):
    """
    Регистрация пользователя по chat_id.
    
    Cтатус запроса:
    - 200 OK - успешная регистрация
    - 400 Bad Request - пользователь с таким chat_id уже зарегистрирован
    - 422 Unprocessable Entity - ошибка валидации входных данных

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)
    
    Входные данные:
    - `username: str` | None - имя пользователя в Telegram
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `referrer_type: str` | None - тип реферера ('user' или 'partner')
    - `referrer_id: str` | None - UUID реферера
    - `ref_link_id: str` | None - UUID реферальной ссылки
    """
    try:
        new_user = await user_service.register_user(dto, session)

        # Automatically create a personal referral link for the new user
        link_dto = ReferralLinkCreate(
            owner_id=new_user.id,
            link_type=LinkType.USER,
            comment="Default user link"
        )
        await referral_service.create_referral_link(link_dto, session)

        return {"ok": True, "user_id": new_user.id, "chat_id": new_user.chat_id}
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{chat_id}", summary="Получение информации о пользователе")
async def get_user(
    chat_id: str,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Получение информации о пользователе по chat_id.
    
    Cтатус запроса:
    - 200 OK - успешное получение информации
    - 404 Not Found - пользователь с таким chat_id не найден
    
    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram

    Выходные данные:
    - `id: int` - внутренний идентификатор пользователя в базе данных
    - `nickname: str` | None - имя пользователя в Telegram
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `coins: int` - количество монет у пользователя
    """
    try:
        return await service.get_user(chat_id, session)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("", 
               status_code=status.HTTP_204_NO_CONTENT, 
               summary="Удаление пользователя")
async def delete_user(
    dto: UserDelete,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Удаление пользователя по chat_id.
    Cтатус запроса:
    - 204 No Content - успешное удаление пользователя
    - 404 Not Found - пользователь с таким chat_id не найден

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    """
    try:
        await service.delete_user(dto, session)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{chat_id}/coins", summary="Получение количества монет пользователя")
async def get_coins(
    chat_id: str,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Получение количества монет пользователя по chat_id.
    
    Cтатус запроса:
    - 200 OK - успешное получение количества монет
    - 404 Not Found - пользователь с таким chat_id не найден

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram

    Выходные данные:
    - `ok: bool` - статус успешности запроса
    - `coins: int` - количество монет у пользователя
    """
    try:
        coins = await service.get_coins(chat_id, session)
        return {"ok": True, "coins": coins}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/coins/minus", summary="Списание одной монеты у пользователя")
async def minus_coin(
    dto: CoinMinus,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Списание одной монеты у пользователя по chat_id.

    Статус запроса:
    - 200 OK - успешное списание монеты
    - 404 Not Found - пользователь с таким chat_id не найден
    - 400 Bad Request - недостаточно монет для списания

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram

    Выходные данные:
    - `ok: bool` - статус успешности запроса
    - `coins: int` - текущее количество монет у пользователя после списания
    """

    try:
        coins = await service.minus_coin(dto, session)
        return {"ok": True, "coins": coins}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/referrer", summary="Установить реферера для пользователя")
async def set_referrer(
    dto: UserReferrerUpdate,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Устанавливает реферера для существующего пользователя, если он еще не установлен.
    """
    try:
        updated_user = await service.set_referrer(dto, session)
        return updated_user
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/coins/plus", summary="Начисление монет пользователю")
async def plus_coins(
    dto: CoinPlus,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Начисление монет пользователю по chat_id.

    Статус запроса:
    - 200 OK - успешное начисление монет
    - 404 Not Found - пользователь с таким chat_id не найден
    - 400 Bad Request - ошибка бизнес-логики (например, превышение максимального количества монет)
    
    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)
    
    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `count: int` - количество монет для начисления (должно быть положительным числом)
    
    Выходные данные:
    - `ok: bool` - статус успешности запроса
    - `coins: int` - текущее количество монет у пользователя после начисления
    """

    try:
        coins = await service.plus_coins(dto, session)
        return {"ok": True, "coins": coins}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

from __future__ import annotations
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_async_session
from api.crud.user.schema import (
    UserRegister, UserDelete, CoinMinus, CoinPlus
)
from api.crud.user import UserService, UserNotFound, BusinessRuleError
from utils.referral import RefLink
from config import ENV


router = APIRouter()
env = ENV()

def get_user_service() -> UserService:
    return UserService()
def get_referral_util() -> "RefLink":
    return RefLink()


@router.post("/register", summary="Регистрация пользователя")
async def register_user(
    dto: UserRegister,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
    referral_util: RefLink = Depends(get_referral_util)
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
    """
    try:
        dto.ref_code = referral_util.generate_ref_code(
            codes=[code.code for code in await service.get_all_ref_codes(session)],
            role=dto.role)
        return await service.register_user(dto, session)
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

@router.patch("/{chat_id}/role", summary="Обновление роли пользователя")
async def update_user_role(
    chat_id: str,
    new_role: Literal["user", "partner"],
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Обновление роли пользователя по chat_id.

    Статус запроса:
    - 200 OK - успешное обновление роли
    - 404 Not Found - пользователь с таким chat_id не найден
    - 400 Bad Request - ошибка бизнес-логики (например, недопустимая роль)

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `new_role: str` - новая роль для пользователя (например, "user" или "partner")

    Выходные данные:
    - `ok: bool` - статус успешности запроса
    - `role: str` - текущая роль пользователя после обновления
    """

    try:
        role = await service.update_user_role(chat_id, new_role, session)
        return {"ok": True, "role": role}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
@router.get("/{chat_id}/ref_code", summary="Получение реферального кода пользователя")
async def get_ref_code(
    chat_id: str,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    """
    Получение реферального кода пользователя по chat_id.
    
    Cтатус запроса:
    - 200 OK - успешное получение реферального кода
    - 404 Not Found - пользователь с таким chat_id не найден
    
    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram

    Выходные данные:
    - `ok: bool` - статус успешности запроса
    - `ref_code: str` | None - реферальный код пользователя, если он есть
    """
    try:
        ref_code = await service.get_ref_code(chat_id, session)
        return {"ok": True, "ref_code": ref_code, "ref_link": f"https://t.me/{env.bot_username}?start={ref_code}" if ref_code else None}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
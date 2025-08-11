from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_async_session
from api.crud.user.schema import (
    UserRegister, UserDelete, CoinMinus, CoinPlus
)
from api.crud.user import UserService, UserNotFound, BusinessRuleError

from api.security import require_bot_service

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_bot_service)])

def get_user_service() -> UserService:
    return UserService()


@router.post("/register")
async def register_user(
    dto: UserRegister,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    try:
        return await service.register_user(dto, session)
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{chat_id}")
async def get_user(
    chat_id: str,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    try:
        return await service.get_user(chat_id, session)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    dto: UserDelete,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    try:
        await service.delete_user(dto, session)
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{chat_id}/coins")
async def get_coins(
    chat_id: str,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    try:
        coins = await service.get_coins(chat_id, session)
        return {"ok": True, "coins": coins}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/coins/minus")
async def minus_coin(
    dto: CoinMinus,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    try:
        coins = await service.minus_coin(dto, session)
        return {"ok": True, "coins": coins}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/coins/plus")
async def plus_coins(
    dto: CoinPlus,
    session: AsyncSession = Depends(get_async_session),
    service: UserService = Depends(get_user_service),
):
    try:
        coins = await service.plus_coins(dto, session)
        return {"ok": True, "coins": coins}
    except UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BusinessRuleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

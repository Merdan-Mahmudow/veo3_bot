from typing import Any, Dict
from fastapi import Depends
from sqlalchemy import insert, select, update, delete, func
from .interface import UserInterface
from sqlalchemy.ext.asyncio import AsyncSession
from .schema import CoinMinus, CoinPlus, UserDelete, UserRead, UserRegister
from api.database import get_async_session
from api.models.user import User


class UserNotFound(Exception): ...
class BusinessRuleError(Exception): ...


class UserService(UserInterface):
    """Бизнес-логика. Не знает про FastAPI и HTTP — только про данные и правила."""
    async def register_user(self, dto: UserRegister, session: AsyncSession) -> Dict[str, Any]:
        # пример: запретить дубли по chat_id
        exists = await session.scalar(select(func.count()).select_from(User).where(User.chat_id == dto.chat_id))
        if exists:
            raise BusinessRuleError("User with this chat_id already exists")

        await session.execute(insert(User).values(dto.model_dump()))
        await session.commit()
        return {"ok": True}

    async def get_user(self, chat_id: str, session: AsyncSession):
        res = await session.execute(select(User).where(User.chat_id == chat_id))
        user = res.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")
        return user

    async def delete_user(self, dto: UserDelete, session: AsyncSession) -> None:
        result = await session.execute(delete(User).where(User.chat_id == dto.chat_id))
        await session.commit()
        if result.rowcount == 0:
            raise UserNotFound("User not found")

    async def get_coins(self, chat_id: str, session: AsyncSession) -> int:
        res = await session.execute(select(User.coins).where(User.chat_id == chat_id))
        coins = res.scalar_one_or_none()
        if coins is None:
            raise UserNotFound("User not found")
        return coins

    async def minus_coin(self, dto: CoinMinus, session: AsyncSession) -> int:
        # защита от ухода в минус на уровне SQL
        stmt = (
            update(User)
            .where(User.chat_id == dto.chat_id, User.coins > 0)
            .values(coins=User.coins - 1)
            .returning(User.coins)
        )
        res = await session.execute(stmt)
        new_value = res.scalar_one_or_none()
        await session.commit()
        if new_value is None:
            # либо пользователя нет, либо coins уже был 0
            # разрулим точнее:
            exists = await session.scalar(select(func.count()).select_from(User).where(User.chat_id == dto.chat_id))
            if not exists:
                raise UserNotFound("User not found")
            raise BusinessRuleError("Coins cannot go below zero")
        return new_value

    async def plus_coins(self, dto: CoinPlus, session: AsyncSession) -> int:
        if dto.count <= 0:
            raise BusinessRuleError("count must be > 0")
        stmt = (
            update(User)
            .where(User.chat_id == dto.chat_id)
            .values(coins=User.coins + dto.count)
            .returning(User.coins)
        )
        res = await session.execute(stmt)
        new_value = res.scalar_one_or_none()
        await session.commit()
        if new_value is None:
            raise UserNotFound("User not found")
        return new_value
    
    async def list_user_chat_ids(self, session: AsyncSession) -> list[str]:
        res = await session.execute(select(User.chat_id))
        chat_ids = res.scalars().all()
        return chat_ids
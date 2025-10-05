from typing import Any, Dict, Literal
from sqlalchemy import insert, select, update, delete, func
from .interface import UserInterface
from sqlalchemy.ext.asyncio import AsyncSession
from .schema import CoinMinus, CoinPlus, UserDelete, UserRegister
from api.models.user import User


class UserNotFound(Exception): ...
class BusinessRuleError(Exception): ...


class UserService(UserInterface):
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
    
    async def get_all_ref_codes(self, session: AsyncSession) -> list:
        res = await session.execute(select(User.ref_code).where(User.ref_code != None))
        codes = res.scalars().all()
        return codes
    
    async def update_user_role(self, chat_id: str, new_role: Literal["user", "partner"], session: AsyncSession) -> None:
        stmt = (
            update(User)
            .where(User.chat_id == chat_id)
            .values(role=new_role)
        )
        res = await session.execute(stmt)
        await session.commit()
        if res.rowcount == 0:
            raise UserNotFound("User not found")
        
    async def get_ref_code(self, chat_id: str, session: AsyncSession) -> str | None:
        res = await session.execute(select(User.ref_code).where(User.chat_id == chat_id))
        code = res.scalar_one_or_none()
        if code is None:
            raise UserNotFound("User not found")
        return code
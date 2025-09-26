import uuid
from typing import Any, Dict
from sqlalchemy import insert, select, update, delete, func
from .interface import UserInterface
from sqlalchemy.ext.asyncio import AsyncSession
from .schema import CoinMinus, CoinPlus, UserDelete, UserRegister
from api.models.user import User
from api.crud.referral_link import get_referral_link
from api.models.partner import Partner


class UserNotFound(Exception): ...
class BusinessRuleError(Exception): ...


class UserService(UserInterface):
    async def register_user(self, dto: UserRegister, session: AsyncSession) -> Dict[str, Any]:
        exists = await session.scalar(select(func.count()).select_from(User).where(User.chat_id == dto.chat_id))
        if exists:
            raise BusinessRuleError("User with this chat_id already exists")

        user_data = dto.model_dump()
        referral_link_str = user_data.pop("referral_link", None)

        referrer_id = None
        if referral_link_str:
            if referral_link_str.startswith("ref_"):
                try:
                    referrer_uuid = uuid.UUID(referral_link_str.split('_')[1])
                    referrer_result = await session.execute(select(User).filter(User.id == referrer_uuid))
                    referrer = referrer_result.scalar_one_or_none()
                    if referrer:
                        user_data['referrer_id'] = referrer.id
                        user_data['coins'] = 1  # Bonus for the new user
                except (ValueError, IndexError):
                    pass  # Invalid referral link format
            else:
                referral_link = await get_referral_link(session, referral_link_str)
                if referral_link and referral_link.partner:
                    user_data['referrer_id'] = referral_link.partner.user_id
                    user_data['referral_link_id'] = referral_link.id
                    user_data['coins'] = 1  # Bonus for the new user

        await session.execute(insert(User).values(**user_data))
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
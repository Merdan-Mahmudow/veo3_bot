from typing import Any, Dict
from sqlalchemy import insert, select, update, delete, func
from .interface import UserInterface
from sqlalchemy.ext.asyncio import AsyncSession
from .schema import CoinMinus, CoinPlus, UserDelete, UserRegister
from api.models.user import User
from api.models.referral import ReferralLink


class UserNotFound(Exception): ...
class BusinessRuleError(Exception): ...


class UserService(UserInterface):
    async def register_user(self, dto: UserRegister, session: AsyncSession) -> User:
        """
        Registers a new user. If referral data is provided, it's validated and saved.
        Returns the created user object.
        """
        # 1. Check for duplicates
        exists = await session.scalar(select(User).where(User.chat_id == dto.chat_id))
        if exists:
            raise BusinessRuleError("User with this chat_id already exists")

        # 2. Validate referral data if provided
        if dto.referrer_id:
            referrer = await session.get(User, dto.referrer_id)
            if not referrer:
                raise BusinessRuleError(f"Referrer with id {dto.referrer_id} not found.")

        if dto.ref_link_id:
            ref_link = await session.get(ReferralLink, dto.ref_link_id)
            if not ref_link:
                raise BusinessRuleError(f"Referral link with id {dto.ref_link_id} not found.")

            # Optional but good practice: check if the link belongs to the referrer
            if dto.referrer_id and ref_link.owner_id != dto.referrer_id:
                raise BusinessRuleError("Referrer ID does not match the owner of the referral link.")

        # 3. Create user
        stmt = insert(User).values(**dto.model_dump(exclude_unset=True)).returning(User)
        result = await session.execute(stmt)
        new_user = result.scalar_one()

        await session.commit()
        await session.refresh(new_user)

        return new_user

    async def get_user(self, chat_id: str, session: AsyncSession):
        res = await session.execute(select(User).where(User.chat_id == chat_id))
        user = res.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")
        return user

    async def set_referrer(self, dto: UserReferrerUpdate, session: AsyncSession) -> User:
        """
        Sets the referrer for an existing user, but only if they don't already have one.
        """
        user = await self.get_user(dto.chat_id, session)
        if user.referrer_id:
            raise BusinessRuleError("User already has a referrer.")

        stmt = (
            update(User)
            .where(User.chat_id == dto.chat_id)
            .values(
                referrer_type=dto.referrer_type,
                referrer_id=dto.referrer_id,
                ref_link_id=dto.ref_link_id,
            )
            .returning(User)
        )
        result = await session.execute(stmt)
        updated_user = result.scalar_one()
        await session.commit()
        await session.refresh(updated_user)
        return updated_user

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
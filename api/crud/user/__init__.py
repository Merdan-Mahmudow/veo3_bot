import uuid
import logging
from typing import Any, Dict
from sqlalchemy import insert, select, update, delete, func
from sqlalchemy.orm import selectinload
from .interface import UserInterface
from sqlalchemy.ext.asyncio import AsyncSession
from .schema import CoinMinus, CoinPlus, UserDelete, UserRegister
from api.models import User, Referral, ReferralLink, Role
from api.models.referral_link import LinkType
from api.models.referral import ReferrerType

class UserNotFound(Exception): ...
class BusinessRuleError(Exception): ...

class UserService(UserInterface):
    async def register_user(self, dto: UserRegister, session: AsyncSession) -> Dict[str, Any]:
        exists_count = await session.scalar(select(func.count(User.id)).where(User.chat_id == dto.chat_id))
        if exists_count > 0:
            raise BusinessRuleError("User with this chat_id already exists")

        # --- Create the User ---
        is_suspicious = False
        if dto.referrer_id:
            try:
                # This check is simplified. A real system might check IP, device ID, etc.
                referrer = await session.get(User, uuid.UUID(dto.referrer_id))
                if referrer and referrer.chat_id == dto.chat_id:
                    is_suspicious = True
                    logging.warning(f"Self-referral detected for chat_id {dto.chat_id}. Marking as suspicious.")
            except (ValueError, TypeError):
                logging.warning(f"Invalid referrer_id format: {dto.referrer_id}")

        new_user = User(
            chat_id=dto.chat_id,
            nickname=dto.nickname,
            is_suspicious=is_suspicious
        )
        session.add(new_user)
        await session.flush()  # Flush to get the new_user.id

        # --- Create the Referral Record (if applicable) ---
        if dto.referrer_id and dto.ref_link_id and dto.referrer_type:
            referral_record = Referral(
                new_user_id=new_user.id,
                referrer_id=uuid.UUID(dto.referrer_id),
                ref_link_id=uuid.UUID(dto.ref_link_id),
                referrer_type=ReferrerType[dto.referrer_type]
            )
            session.add(referral_record)

        # --- Assign Default Role ---
        user_role = await session.scalar(select(Role).where(Role.name == 'user'))
        if not user_role:
            user_role = Role(name='user')
            session.add(user_role)
        new_user.roles.append(user_role)

        # --- Create Default Referral Link for the new user ---
        default_link = ReferralLink(
            owner_id=new_user.id,
            link_type=LinkType.user,
            token=uuid.uuid4().hex,  # Generate a unique, random token
            comment="Default user link"
        )
        session.add(default_link)

        await session.commit()
        return {"status": "ok", "user_id": new_user.id}

    async def get_user(self, chat_id: str, session: AsyncSession):
        res = await session.execute(select(User).where(User.chat_id == chat_id))
        user = res.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")
        return user

    async def delete_user(self, dto: UserDelete, session: AsyncSession) -> None:
        result = await session.execute(delete(User).where(User.chat_id == dto.chat_id))
        if result.rowcount == 0:
            raise UserNotFound("User not found")
        await session.commit()

    async def get_coins(self, chat_id: str, session: AsyncSession) -> int:
        coins = await session.scalar(select(User.coins).where(User.chat_id == chat_id))
        if coins is None:
            raise UserNotFound("User not found")
        return coins

    async def minus_coin(self, dto: CoinMinus, session: AsyncSession) -> int:
        stmt = update(User).where(User.chat_id == dto.chat_id, User.coins > 0).values(coins=User.coins - 1).returning(User.coins)
        new_value = await session.scalar(stmt)
        if new_value is None:
            exists = await session.scalar(select(func.count(User.id)).where(User.chat_id == dto.chat_id))
            if not exists:
                raise UserNotFound("User not found")
            raise BusinessRuleError("Coins cannot go below zero")
        await session.commit()
        return new_value

    async def plus_coins(self, dto: CoinPlus, session: AsyncSession) -> int:
        if dto.count <= 0:
            raise BusinessRuleError("count must be > 0")
        stmt = update(User).where(User.chat_id == dto.chat_id).values(coins=User.coins + dto.count).returning(User.coins)
        new_value = await session.scalar(stmt)
        if new_value is None:
            raise UserNotFound("User not found")
        await session.commit()
        return new_value
    
    async def list_user_chat_ids(self, session: AsyncSession) -> list[str]:
        res = await session.execute(select(User.chat_id))
        return res.scalars().all()
import logging
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
from utils.referral import ReferralService as LinkGenerationService
from api.models.role import user_roles


class UserNotFound(Exception): ...
class BusinessRuleError(Exception): ...

class UserService(UserInterface):
    async def register_user(self, dto: UserRegister, session: AsyncSession) -> Dict[str, Any]:
        # транзакция с автокоммитом/автороллбеком
        async with session.begin():
            exists_count = await session.scalar(
                select(func.count(User.id)).where(User.chat_id == dto.chat_id)
            )
            if exists_count and exists_count > 0:
                # маппь на 409, 400 — как удобнее
                raise BusinessRuleError("User with this chat_id already exists")

            user_data = dto.model_dump(exclude_unset=True)

            # anti-fraud
            is_suspicious = False
            if dto.referrer_id:
                referrer = await session.get(User, uuid.UUID(dto.referrer_id))
                if referrer and referrer.chat_id == dto.chat_id:
                    is_suspicious = True
                    logging.warning("Self-referral detected for chat_id %s. Marking as suspicious.", dto.chat_id)

            user_data['is_suspicious'] = is_suspicious

            # создаём пользователя
            new_user = User(**user_data)
            session.add(new_user)
            await session.flush()  # нужен new_user.id

            # роль "user" — get or create
            user_role = await session.scalar(select(Role).where(Role.name == 'user').limit(1))
            if not user_role:
                user_role = Role(name='user')
                session.add(user_role)
                await session.flush()  # нужен user_role.id

            # ВАЖНО: связь через таблицу, без .roles.append(...)
            await session.execute(
                insert(user_roles).values(user_id=new_user.id, role_id=user_role.id)
            )

            # дефолтная реф-ссылка
            link_generator = LinkGenerationService()
            token = link_generator._sign_payload(f"user:{new_user.id}")

            default_link = ReferralLink(
                owner_id=new_user.id,
                link_type=LinkType.user,
                token=token,
                comment="Default user link",
            )
            session.add(default_link)
            # commit выполнит async-flush сам (из-за async with session.begin())

        # вне транзакции доступ к PK безопасен
        return {"status": "ok", "user_id": str(new_user.id)}
    
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
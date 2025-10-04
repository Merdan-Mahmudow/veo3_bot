from typing import Any, Dict
from sqlalchemy import insert, select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from .interface import UserInterface
from sqlalchemy.ext.asyncio import AsyncSession
from .schema import CoinMinus, CoinPlus, UserDelete, UserRegister
from api.models import User, ReferralLink, Referral
from api.models.user import ReferrerType


class UserNotFound(Exception): ...
class BusinessRuleError(Exception): ...


class UserService(UserInterface):
    async def register_user(self, dto: UserRegister, session: AsyncSession) -> Dict[str, Any]:
        user_data = dto.model_dump()
        referral_code = user_data.pop("referral_code", None)

        new_user = User(**user_data)
        session.add(new_user)

        if referral_code:
            ref_link_query = await session.execute(
                select(ReferralLink).where(ReferralLink.token == referral_code)
            )
            ref_link = ref_link_query.scalar_one_or_none()

            if ref_link:
                # Откладываем создание реферальной записи до коммита
                # SQLAlchemy обработает зависимости
                new_user.referrer_id = ref_link.owner_id
                new_user.ref_link_id = ref_link.id
                new_user.referrer_type = ReferrerType[ref_link.link_type.name]

                referral_record = Referral(
                    new_user=new_user,
                    referrer_id=ref_link.owner_id,
                    ref_link_id=ref_link.id,
                    referrer_type=ref_link.link_type.name
                )
                session.add(referral_record)

        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise BusinessRuleError("User with this chat_id already exists")

        return {"ok": True, "created": True}

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

    async def find_user(self, identifier: str, session: AsyncSession):
        """
        Ищет пользователя по chat_id или nickname.
        """
        query = select(User).where(
            (User.chat_id == identifier) | (User.nickname == identifier)
        )
        res = await session.execute(query)
        user = res.scalar_one_or_none()
        if not user:
            raise UserNotFound("User not found")
        return user

    async def get_user_by_id(self, user_id: str, session: AsyncSession):
        """
        Получает пользователя по UUID.
        """
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFound("User not found")
        return user

    async def set_user_role(self, user_id: str, role: str, session: AsyncSession):
        """
        Устанавливает роль пользователю.
        """
        user = await session.get(User, user_id)
        if not user:
            raise UserNotFound("User not found")

        # Валидация роли
        try:
            from api.models.user import UserRole
            user.role = UserRole[role.upper()]
        except KeyError:
            raise BusinessRuleError(f"Invalid role: {role}")

        session.add(user)
        await session.commit()
        return {"ok": True}

    async def get_my_referral_info(self, chat_id: str, session: AsyncSession) -> dict:
        user = await self.get_user(chat_id, session)

        link_query = await session.execute(
            select(ReferralLink).where(ReferralLink.owner_id == user.id, ReferralLink.link_type == 'USER')
        )
        link = link_query.scalar_one_or_none()

        referrals_count_query = await session.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == user.id)
        )
        referrals_count = referrals_count_query.scalar_one_or_none() or 0

        # Считаем уникальных пользователей, которые были приглашены и сделали хотя бы одну покупку
        purchased_referrals_query = await session.execute(
            select(func.count(func.distinct(Purchase.user_id)))
            .join(User, Purchase.user_id == User.id)
            .where(User.referrer_id == user.id)
        )
        referrals_purchased = purchased_referrals_query.scalar_one_or_none() or 0

        # Считаем бонусы, полученные этим пользователем как реферером
        from api.models import CoinBonusLedger
        bonuses_earned_query = await session.execute(
            select(func.sum(CoinBonusLedger.coins))
            .where(CoinBonusLedger.receiver_id == user.id) # Пользователь - получатель бонуса
        )
        bonuses_earned = bonuses_earned_query.scalar_one_or_none() or 0

        return {
            "link": link,
            "referrals_count": referrals_count,
            "referrals_purchased": referrals_purchased,
            "bonuses_earned": bonuses_earned,
        }
from __future__ import annotations
import enum, uuid
from typing import List, Optional
from sqlalchemy import UUID, Boolean, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base
from api.models.role import Role, user_roles
from api.models.referral_link import ReferralLink

class ReferrerType(enum.Enum):
    user = "user"
    partner = "partner"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    coins: Mapped[int] = mapped_column(Integer, default=0)

    # ВАЖНО: имя enum-типов совпадает с тем, что в миграции (referrertype)
    referrer_type: Mapped[Optional[ReferrerType]] = mapped_column(SAEnum(ReferrerType, name="referrertype"), nullable=True)
    referrer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_link_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("referral_links.id"), nullable=True)

    first_payment_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # self-FK: явно указываем foreign_keys и remote_side
    referrer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys="[User.referrer_id]",
        remote_side="[User.id]",
        back_populates="referrals",
    )
    referrals: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys="[User.referrer_id]",
        back_populates="referrer",
    )

    # Пользователь ПРИШЁЛ по конкретной ссылке (User.referral_link_id -> ReferralLink.id)
    referral_link: Mapped[Optional["ReferralLink"]] = relationship(
        "ReferralLink",
        primaryjoin="User.referral_link_id == ReferralLink.id",
        foreign_keys="[User.referral_link_id]",
        back_populates="referred_users",
    )

    # Пользователь ВЛАДЕЕТ множеством ссылок (ReferralLink.owner_id -> User.id)
    referral_links: Mapped[List["ReferralLink"]] = relationship(
        "ReferralLink",
        primaryjoin="User.id == ReferralLink.owner_id",
        foreign_keys="[ReferralLink.owner_id]",
        back_populates="owner",
        cascade="all, delete-orphan",   # опционально
    )

    roles = relationship("Role", secondary=user_roles, back_populates="users")

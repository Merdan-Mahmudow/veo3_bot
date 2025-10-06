import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import UUID, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
# avoid importing User to prevent cycles; use string annotations in relationships


class ReferralLinkType(enum.Enum):
    USER = "user"
    PARTNER = "partner"


class ReferralLink(Base):
    __tablename__ = "referral_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    link_type: Mapped[ReferralLinkType] = mapped_column(Enum(ReferralLinkType), nullable=False)
    percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()", nullable=False)

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="owned_referral_links",
        foreign_keys=[owner_id]  # указываем локальный столбец owner_id как FK для отношения
    )
    referred_users: Mapped[List["User"]] = relationship(back_populates="referral_link")


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    new_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    referrer_type: Mapped[str] = mapped_column(Enum("user", "partner", name="referrertype"), nullable=False)
    referrer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ref_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referral_links.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()", nullable=False)

    # Relationships - use string annotations to avoid cycles
    new_user: Mapped["User"] = relationship(foreign_keys=[new_user_id])
    referrer: Mapped["User"] = relationship(foreign_keys=[referrer_id])
    link: Mapped["ReferralLink"] = relationship(foreign_keys=[ref_link_id])
from .base import Base
import enum
import uuid
from sqlalchemy import UUID, DateTime, Enum, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional


class UserRole(enum.Enum):
    USER = "user"
    PARTNER = "partner"
    ADMIN = "admin"

class ReferrerType(enum.Enum):
    USER = "user"
    PARTNER = "partner"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Referral system fields
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"), 
        default=UserRole.USER, 
        server_default=text(f"'{UserRole.USER.value}'"),
        nullable=False,
    )
    referrer_type: Mapped[Optional[ReferrerType]] = mapped_column(Enum(ReferrerType), nullable=True)
    referrer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    ref_link_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("referral_links.id"), nullable=True)

    # Relationships
    # User who referred me
    referrer: Mapped[Optional["User"]] = relationship(back_populates="referrals", remote_side=[id])
    # Users whom I referred
    referrals: Mapped[List["User"]] = relationship(back_populates="referrer")

    # The specific link that referred me
    referral_link: Mapped[Optional["ReferralLink"]] = relationship(foreign_keys=[ref_link_id], back_populates="referred_users")

    # Links that I own
    owned_referral_links: Mapped[List["ReferralLink"]] = relationship(
        "ReferralLink",
        back_populates="owner",
        foreign_keys='[ReferralLink.owner_id]'  # явное указание FK для снятия неоднозначности
    )

    purchases: Mapped[List["Purchase"]] = relationship(back_populates="user")

    payout_requests: Mapped[List["PayoutRequest"]] = relationship(back_populates="partner")

    partner_balance: Mapped[Optional["PartnerBalance"]] = relationship(back_populates="partner")
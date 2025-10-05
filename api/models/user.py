import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID as UUID_DB
from sqlalchemy import Enum as Enum_DB
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database.base import Base

if TYPE_CHECKING:
    from api.models.referral import (
        AuditLog,
        PartnerBalance,
        PartnerCommissionLedger,
        PayoutRequest,
        Purchase,
        ReferralLink,
    )


class UserRole(str, enum.Enum):
    USER = "user"
    PARTNER = "partner"
    ADMIN = "admin"


class ReferrerType(str, enum.Enum):
    USER = "user"
    PARTNER = "partner"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Referral system fields
    role: Mapped[UserRole] = mapped_column(Enum_DB(UserRole, name="user_role"), default=UserRole.USER, nullable=False)

    referrer_type: Mapped[ReferrerType | None] = mapped_column(Enum_DB(ReferrerType, name="referrer_type"), nullable=True)
    referrer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ref_link_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("referral_links.id"), nullable=True)

    # Relationships
    referrer: Mapped["User | None"] = relationship(remote_side=[id], foreign_keys=[referrer_id])
    referral_link: Mapped["ReferralLink | None"] = relationship(foreign_keys=[ref_link_id], back_populates="referred_users")

    owned_referral_links: Mapped[list["ReferralLink"]] = relationship(foreign_keys="ReferralLink.owner_id", back_populates="owner")

    purchases: Mapped[list["Purchase"]] = relationship(back_populates="user")

    commission_earnings: Mapped[list["PartnerCommissionLedger"]] = relationship(foreign_keys="PartnerCommissionLedger.partner_id", back_populates="partner")

    partner_balance: Mapped["PartnerBalance | None"] = relationship(back_populates="partner")

    payout_requests: Mapped[list["PayoutRequest"]] = relationship(back_populates="partner")

    audit_logs: Mapped[list["AuditLog"]] = relationship(foreign_keys="AuditLog.actor_id")

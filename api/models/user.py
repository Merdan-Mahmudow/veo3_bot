from __future__ import annotations
from api.models import Base
from api.models.role import Role, user_roles
import enum

from datetime import datetime
import uuid
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Integer, Text

from sqlalchemy.orm import mapped_column, Mapped, relationship


class ReferrerType(enum.Enum):
    user = "user"
    partner = "partner"

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    referrer_type: Mapped[ReferrerType] = mapped_column(Enum(ReferrerType), nullable=True)
    referrer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referral_links.id"), nullable=True)
    first_payment_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    referrer = relationship("User", back_populates="referred_users", remote_side=[id])
    referred_users = relationship("User", back_populates="referrer")
    referral_link = relationship("ReferralLink", back_populates="users")
    roles = relationship("Role", secondary=user_roles, back_populates="users")

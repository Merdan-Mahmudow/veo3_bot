from __future__ import annotations
from typing import TYPE_CHECKING
from api.models import Base
from api.models.role import user_roles # Keep the association table import
import uuid
from sqlalchemy import UUID, Boolean, String, Integer
from sqlalchemy.orm import mapped_column, Mapped, relationship

if TYPE_CHECKING:
    from api.models.referral import Referral
    from api.models.role import Role
    from api.models.referral_link import ReferralLink

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_suspicious: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # The referral event that brought this user to the bot. One-to-one.
    referral_record: Mapped["Referral"] = relationship(back_populates="user", foreign_keys="Referral.new_user_id", cascade="all, delete-orphan")

    # A user can own multiple referral links (e.g., as a partner)
    referral_links: Mapped[List["ReferralLink"]] = relationship(back_populates="owner")

    # A user can have multiple roles (user, partner, admin)
    roles: Mapped[List["Role"]] = relationship(secondary=user_roles, back_populates="users")
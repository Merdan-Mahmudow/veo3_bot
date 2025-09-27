from __future__ import annotations
import enum
import uuid
from typing import TYPE_CHECKING, List
from sqlalchemy import UUID, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base

if TYPE_CHECKING:
    from api.models.user import User

class LinkType(enum.Enum):
    user = "user"
    partner = "partner"

class ReferralLink(Base):
    __tablename__ = "referral_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    link_type: Mapped[LinkType] = mapped_column(Enum(LinkType), nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=True)  # Null for 'user' type
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    comment: Mapped[str] = mapped_column(String, nullable=True)

    # The user who owns this link
    owner: Mapped["User"] = relationship(back_populates="referral_links")
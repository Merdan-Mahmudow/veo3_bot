import enum
import uuid
from sqlalchemy import UUID, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base


class LinkType(enum.Enum):
    user = "user"
    partner = "partner"


class ReferralLink(Base):
    __tablename__ = "referral_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    link_type: Mapped[LinkType] = mapped_column(Enum(LinkType), nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=True)  # Null for 'user' type
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    comment: Mapped[str] = mapped_column(String, nullable=True)

    owner = relationship("User", back_populates="referral_links")
    users = relationship("User", back_populates="referral_link")

from api.models.user import User
User.referral_links = relationship("ReferralLink", order_by=ReferralLink.id, back_populates="owner")
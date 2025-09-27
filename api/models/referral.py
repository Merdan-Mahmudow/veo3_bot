import uuid
import enum
from datetime import datetime
from sqlalchemy import UUID, Enum, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base

class ReferrerType(enum.Enum):
    user = "user"
    partner = "partner"

class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    new_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False) # A user can only be referred once
    referrer_type: Mapped[ReferrerType] = mapped_column(Enum(ReferrerType), nullable=False)
    referrer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ref_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referral_links.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # The user who was referred
    user = relationship("User", foreign_keys=[new_user_id], back_populates="referral_record")
    # The user who did the referring
    referrer = relationship("User", foreign_keys=[referrer_id])
    # The link that was used
    link = relationship("ReferralLink")
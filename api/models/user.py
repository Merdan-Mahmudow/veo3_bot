from api.models import Base

from datetime import datetime
import uuid
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Integer, Text

from sqlalchemy.orm import mapped_column, Mapped, relationship


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    referrer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=True)
    referral_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referral_links.id"), nullable=True)
    first_payment_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    referrer = relationship("User", back_populates="referred_users", remote_side=[id])
    referred_users = relationship("User", back_populates="referrer")
    referral_link = relationship("ReferralLink")

import uuid
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Integer, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship
from api.models import Base
from datetime import datetime


class Partner(Base):
    __tablename__ = "partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)

    user = relationship("User")
    referral_links = relationship("ReferralLink", back_populates="partner")
    transactions = relationship("Transaction", back_populates="partner")
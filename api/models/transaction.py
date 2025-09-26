import uuid
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Integer, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship
from api.models import Base
from datetime import datetime


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    partner = relationship("Partner", back_populates="transactions")
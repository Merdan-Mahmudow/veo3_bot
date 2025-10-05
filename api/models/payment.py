import uuid
from datetime import datetime

from sqlalchemy import UUID as UUID_DB, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from api.database.base import Base
from api.models.user import User


class PendingPayment(Base):
    __tablename__ = "pending_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    yookassa_payment_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(String, nullable=False) # Storing as string from Yookassa
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship()
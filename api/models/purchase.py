import uuid
from sqlalchemy import UUID, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    yookassa_payment_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False, server_default="RUB")
    is_first_for_user: Mapped[bool] = mapped_column(Boolean, nullable=False)

    user = relationship("User")
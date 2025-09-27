import enum
import uuid
from sqlalchemy import Enum, UUID, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base


class PayoutStatus(enum.Enum):
    requested = "requested"
    approved = "approved"
    rejected = "rejected"
    paid = "paid"


class PayoutRequest(Base):
    __tablename__ = "payout_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(Enum(PayoutStatus), default=PayoutStatus.requested)
    requisites_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    partner = relationship("User")
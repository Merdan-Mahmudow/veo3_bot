import enum
import uuid
from sqlalchemy import UUID, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base


class CommissionStatus(enum.Enum):
    accrued = "accrued"
    hold = "hold"
    available = "available"
    paid_out = "paid_out"
    reversed = "reversed"


class PartnerCommissionLedger(Base):
    __tablename__ = "partner_commission_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    ref_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referral_links.id"), nullable=False)
    base_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[CommissionStatus] = mapped_column(Enum(CommissionStatus), default=CommissionStatus.accrued)
    reason: Mapped[str] = mapped_column(String, nullable=True)

    partner = relationship("User", foreign_keys=[partner_id])
    user = relationship("User", foreign_keys=[user_id])
    purchase = relationship("Purchase")
    referral_link = relationship("ReferralLink")
import uuid
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Integer, Text
from sqlalchemy.orm import mapped_column, Mapped, relationship
from api.models import Base


class ReferralLink(Base):
    __tablename__ = "referral_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("partners.id"), nullable=False)
    link: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    percentage: Mapped[int] = mapped_column(Integer, nullable=False)

    partner = relationship("Partner", back_populates="referral_links")
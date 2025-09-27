import uuid
from sqlalchemy import UUID, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base


class PartnerBalance(Base):
    __tablename__ = "partner_balances"

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance_minor: Mapped[int] = mapped_column(Integer, default=0)
    hold_minor: Mapped[int] = mapped_column(Integer, default=0)

    partner = relationship("User")
import uuid
from sqlalchemy import UUID, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base


class CoinBonusLedger(Base):
    __tablename__ = "coin_bonus_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    giver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=1)

    giver = relationship("User", foreign_keys=[giver_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
    purchase = relationship("Purchase")
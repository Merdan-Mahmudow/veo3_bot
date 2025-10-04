import enum
import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models import Base
from api.models.user import User
from api.models.referral import ReferralLink


class PayoutStatus(enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    is_first_for_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="purchases")
    commission_ledger_entry: Mapped["PartnerCommissionLedger"] = relationship(back_populates="purchase")
    coin_bonus_ledger_entries: Mapped[list["CoinBonusLedger"]] = relationship(back_populates="purchase")


class CoinBonusLedger(Base):
    __tablename__ = "coin_bonus_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    giver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    coins: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()", nullable=False)

    # Relationships
    giver: Mapped["User"] = relationship(foreign_keys=[giver_id])
    receiver: Mapped["User"] = relationship(foreign_keys=[receiver_id])
    purchase: Mapped["Purchase"] = relationship(back_populates="coin_bonus_ledger_entries")


class PartnerCommissionLedger(Base):
    __tablename__ = "partner_commission_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchases.id"), nullable=False, unique=True)
    ref_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referral_links.id"), nullable=False)
    base_amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()", nullable=False)

    # Relationships
    partner: Mapped["User"] = relationship(foreign_keys=[partner_id])
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    purchase: Mapped["Purchase"] = relationship(back_populates="commission_ledger_entry")
    ref_link: Mapped["ReferralLink"] = relationship()


class PartnerBalance(Base):
    __tablename__ = "partner_balances"

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hold_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=datetime.now, nullable=False, default=datetime.now)

    # Relationships
    partner: Mapped["User"] = relationship(back_populates="partner_balance")


class PayoutRequest(Base):
    __tablename__ = "payout_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(Enum(PayoutStatus), default=PayoutStatus.REQUESTED, nullable=False)
    requisites_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()", nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    partner: Mapped["User"] = relationship(back_populates="payout_requests")
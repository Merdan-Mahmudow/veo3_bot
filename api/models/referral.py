import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    UUID as UUID_DB,
    BigInteger,
    Boolean,
    DateTime,
    Enum as Enum_DB,
    ForeignKey,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from api.database.base import Base


class LinkType(str, enum.Enum):
    USER = "user"
    PARTNER = "partner"


class LedgerStatus(str, enum.Enum):
    ACCRUED = "accrued"
    REVERSED = "reversed"


class CommissionStatus(str, enum.Enum):
    ACCRUED = "accrued"
    HOLD = "hold"
    AVAILABLE = "available"
    PAID_OUT = "paid_out"
    REVERSED = "reversed"


class PayoutStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class LinkRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class LinkRequest(Base):
    __tablename__ = "link_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    requested_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[LinkRequestStatus] = mapped_column(Enum_DB(LinkRequestStatus, name="link_request_status"), default=LinkRequestStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    partner: Mapped["User"] = relationship(foreign_keys=[partner_id])
    admin: Mapped["User | None"] = relationship(foreign_keys=[processed_by_admin_id])


class ReferralLink(Base):
    __tablename__ = "referral_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    link_type: Mapped[LinkType] = mapped_column(Enum_DB(LinkType, name="link_type"), nullable=False)
    percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id], back_populates="owned_referral_links")
    referred_users: Mapped[list["User"]] = relationship(back_populates="referral_link")
    commission_entries: Mapped[list["PartnerCommissionLedger"]] = relationship(back_populates="referral_link")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    yookassa_payment_id: Mapped[str] = mapped_column(String, nullable=True, unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    is_first_for_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="purchases")
    coin_bonus_ledger_entries: Mapped[list["CoinBonusLedger"]] = relationship(back_populates="purchase")
    partner_commission_ledger_entry: Mapped["PartnerCommissionLedger"] = relationship(back_populates="purchase")


class CoinBonusLedger(Base):
    __tablename__ = "coin_bonus_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    giver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchases.id"), nullable=False, unique=True)
    coins: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[LedgerStatus] = mapped_column(Enum_DB(LedgerStatus, name="ledger_status"), default=LedgerStatus.ACCRUED, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    giver: Mapped["User"] = relationship(foreign_keys=[giver_id])
    receiver: Mapped["User"] = relationship(foreign_keys=[receiver_id])
    purchase: Mapped["Purchase"] = relationship(back_populates="coin_bonus_ledger_entries")


class PartnerCommissionLedger(Base):
    __tablename__ = "partner_commission_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchases.id"), nullable=False, unique=True)
    ref_link_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referral_links.id"), nullable=False)
    base_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    percent: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[CommissionStatus] = mapped_column(Enum_DB(CommissionStatus, name="commission_status"), default=CommissionStatus.ACCRUED, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    partner: Mapped["User"] = relationship(foreign_keys=[partner_id], back_populates="commission_earnings")
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    purchase: Mapped["Purchase"] = relationship(back_populates="partner_commission_ledger_entry")
    referral_link: Mapped["ReferralLink"] = relationship(back_populates="commission_entries")


class PartnerBalance(Base):
    __tablename__ = "partner_balances"

    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    balance_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    hold_minor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    partner: Mapped["User"] = relationship(back_populates="partner_balance")


class PayoutRequest(Base):
    __tablename__ = "payout_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(Enum_DB(PayoutStatus, name="payout_status"), default=PayoutStatus.REQUESTED, nullable=False)
    requisites_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    partner: Mapped["User"] = relationship(back_populates="payout_requests")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID_DB(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_id])
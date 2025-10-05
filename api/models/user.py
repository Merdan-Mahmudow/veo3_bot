from api.models import Base

from datetime import datetime
import uuid
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Integer, Text, ARRAY

from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    role: Mapped[str] = mapped_column(String, default="user")
    ref_code: Mapped[str] = mapped_column(String, nullable=True)
    referred_by: Mapped[str] = mapped_column(String, nullable=True)
    first_time: Mapped[bool] = mapped_column(Boolean, default=False, server_default="true")
    partner_codes: Mapped[list["PartnerReferral"]] = relationship(back_populates="user")
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, server_default="0.0")

class PartnerReferral(Base):
    __tablename__ = "ref_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    user_chat_id: Mapped[str] = mapped_column(String, nullable=False)
    user: Mapped["User"] = relationship(back_populates="partner_codes")
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    percentage: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(String, default=datetime.utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
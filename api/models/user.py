from api.models import Base

from datetime import datetime
import uuid
from sqlalchemy import UUID, Boolean, DateTime, Enum, ForeignKey, Numeric, String, Integer, Text

from sqlalchemy.orm import mapped_column, Mapped

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nickname: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str] = mapped_column(String, nullable=False)
    coins: Mapped[int] = mapped_column(Integer, default=0)

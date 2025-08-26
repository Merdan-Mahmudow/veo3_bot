from api.models import Base

from datetime import datetime
import uuid
from sqlalchemy import UUID, Boolean, DateTime, String, Integer, Text

from sqlalchemy.orm import mapped_column, Mapped

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    chat_id: Mapped[str] = mapped_column(String, nullable=False)
    raw: Mapped[dict] = mapped_column(Text, nullable=True)
    is_video: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

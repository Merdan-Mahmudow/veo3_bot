import uuid
from sqlalchemy import UUID, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from api.models import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # This is a placeholder model to satisfy dependencies.
    # It can be expanded later if needed.
    related_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=True)
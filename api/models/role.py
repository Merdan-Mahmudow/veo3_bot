import uuid
from sqlalchemy import UUID, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.models import Base
from api.models.user import UserRole


class Role(Base):
    __tablename__ = "roles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), primary_key=True)

    # Relationships
    user: Mapped["User"] = relationship()
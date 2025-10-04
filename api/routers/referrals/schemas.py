from pydantic import BaseModel, Field
import uuid

class CreateUserLinkSchema(BaseModel):
    chat_id: str

class CreatePartnerLinkSchema(BaseModel):
    owner_id: uuid.UUID
    percent: int = Field(..., gt=0, le=100) # Процент от 1 до 100
    comment: str | None = None
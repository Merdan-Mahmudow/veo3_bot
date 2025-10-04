import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any

from api.models.payments import PayoutStatus

class PayoutRequestCreate(BaseModel):
    chat_id: str
    amount_minor: int
    requisites_json: Dict[str, Any]

class PayoutRequestRead(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    amount_minor: int
    status: PayoutStatus
    requisites_json: Dict[str, Any]
    created_at: datetime
    processed_at: datetime | None = None

    class Config:
        from_attributes = True
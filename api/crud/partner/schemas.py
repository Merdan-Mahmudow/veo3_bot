from typing import Optional
from pydantic import BaseModel

class PartnerCreate(BaseModel):
    user_chat_id: str
    percentage: int
    active: Optional[bool] = True

    class Config:
        from_attributes = True
import uuid
from pydantic import BaseModel
from typing import List

class PartnerLinkRead(BaseModel):
    id: uuid.UUID
    token: str
    percent: int | None
    comment: str | None

    class Config:
        from_attributes = True

class PartnerDashboardData(BaseModel):
    total_referrals: int
    total_purchases: int
    total_commission_minor: int
    balance_minor: int
    hold_minor: int

    class Config:
        from_attributes = True
import uuid
from pydantic import BaseModel, Field
from api.models.referral import LinkType, PayoutStatus
from api.models.user import UserRole, ReferrerType


class ReferralLinkCreate(BaseModel):
    owner_id: uuid.UUID
    link_type: LinkType
    percent: int | None = Field(default=None, ge=10, le=50)
    comment: str | None = None
    actor_chat_id: str | None = None


class PayoutRequestCreate(BaseModel):
    partner_id: uuid.UUID
    amount_minor: int = Field(gt=0)
    requisites_json: dict


class PayoutRequestUpdate(BaseModel):
    status: PayoutStatus
    actor_chat_id: str


class UserRoleUpdate(BaseModel):
    user_id: uuid.UUID
    role: UserRole
    actor_chat_id: str


class UserReferrerUpdate(BaseModel):
    user_id: uuid.UUID
    referrer_type: ReferrerType | None
    referrer_id: uuid.UUID | None
    ref_link_id: uuid.UUID | None


class PartnerStats(BaseModel):
    registrations_count: int
    total_commission_minor: int


class LinkRequestCreate(BaseModel):
    partner_id: uuid.UUID
    requested_percent: int = Field(ge=10, le=50)
    comment: str | None = None


class LinkRequestUpdate(BaseModel):
    actor_chat_id: str
    status: str # We'll validate this in the endpoint
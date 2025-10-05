from pydantic import BaseModel
import uuid
from api.models.user import ReferrerType, UserRole


class UserSchema(BaseModel):
    id: uuid.UUID
    nickname: str
    chat_id: str
    coins: int
    role: UserRole
    referrer_type: ReferrerType | None = None
    referrer_id: uuid.UUID | None = None
    ref_link_id: uuid.UUID | None = None

    class Config:
        from_attributes = True


class UserRegister(BaseModel):
    nickname: str
    chat_id: str
    referrer_type: ReferrerType | None = None
    referrer_id: uuid.UUID | None = None
    ref_link_id: uuid.UUID | None = None

    class Config:
        from_attributes = True


class UserRead(UserSchema):
    ...

    class Config:
        from_attributes = True


class UserReferrerUpdate(BaseModel):
    chat_id: str
    referrer_type: ReferrerType
    referrer_id: uuid.UUID
    ref_link_id: uuid.UUID


class UserDelete(BaseModel):
    chat_id: str

    class Config:
        from_attributes = True


class CoinsCount(BaseModel):
    chat_id: str
    count: int

    class Config:
        from_attributes = True

class CoinMinus(BaseModel):
    chat_id: str

    class Config:
        from_attributes = True

class CoinPlus(BaseModel):
    chat_id: str
    count: int

    class Config:
        from_attributes = True
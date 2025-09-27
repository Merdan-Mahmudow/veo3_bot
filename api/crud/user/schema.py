from pydantic import BaseModel, Field
from typing import List, Optional

class UserBase(BaseModel):
    chat_id: str
    nickname: Optional[str] = None

class UserRegister(UserBase):
    referrer_type: Optional[str] = None
    referrer_id: Optional[str] = None
    ref_link_id: Optional[str] = None

class UserDelete(BaseModel):
    chat_id: str

class CoinMinus(BaseModel):
    chat_id: str

class CoinPlus(BaseModel):
    chat_id: str
    count: int = Field(..., gt=0)

class UserRolesOut(BaseModel):
    roles: List[str]

    class Config:
        from_attributes = True
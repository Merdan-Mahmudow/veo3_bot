from pydantic import BaseModel
from typing import Optional, Dict, Any

class UserSchema(BaseModel):
    id: int
    nickname: str
    chat_id: str
    coins: int
    
    class Config:
        from_attributes = True

class UserRegister(BaseModel):
    nickname: str
    chat_id: str
    referral_code: Optional[str] = None
    class Config:
        from_attributes = True

class UserRead(UserSchema):
    ...

    class Config:
        from_attributes = True

class UserUpdateRole(BaseModel):
    role: str

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
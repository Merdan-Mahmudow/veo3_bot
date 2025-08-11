from pydantic import BaseModel

class UserSchema(BaseModel):
    id: int
    nickname: str
    chat_id: str
    coins: int

class UserRegister(BaseModel):
    nickname: str
    chat_id: str

class UserRead(UserSchema):
    ...

class UserDelete(BaseModel):
    chat_id: str


class CoinsCount(BaseModel):
    chat_id: str
    count: int

class CoinMinus(BaseModel):
    chat_id: str

class CoinPlus(BaseModel):
    chat_id: str
    count: int
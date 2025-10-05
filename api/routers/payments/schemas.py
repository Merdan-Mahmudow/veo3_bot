from pydantic import BaseModel


class CreatePayment(BaseModel):
    chat_id: str
    amount: str
    desc: str
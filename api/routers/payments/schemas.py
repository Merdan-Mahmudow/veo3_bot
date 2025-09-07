from pydantic import BaseModel


class CreatePayment(BaseModel):
    amount: str
    desc: str
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid
from datetime import datetime


class CreatePayment(BaseModel):
    amount: str
    desc: str
    chat_id: str # Добавили chat_id для связи платежа с пользователем


# YooKassa Webhook Schemas
class Amount(BaseModel):
    value: str
    currency: str


class Recipient(BaseModel):
    account_id: str
    gateway_id: str


class PaymentMethod(BaseModel):
    type: str
    id: str
    saved: bool
    title: Optional[str] = None
    card: Optional[Dict[str, Any]] = None


class PaymentObject(BaseModel):
    id: str
    status: str
    amount: Amount
    income_amount: Optional[Amount] = None
    description: Optional[str] = None
    recipient: Recipient
    payment_method: PaymentMethod
    captured_at: datetime
    created_at: datetime
    test: bool
    paid: bool
    refundable: bool
    metadata: Optional[Dict[str, Any]] = Field(default_fatory=dict)


class YooKassaNotification(BaseModel):
    type: str
    event: str
    object: PaymentObject
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

from api.models.user import User
from api.models.partner import Partner
from api.models.referral_link import ReferralLink
from api.models.transaction import Transaction
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# Import all models here so that Alembic can see them
from api.models.user import User
from api.models.role import Role
from api.models.referral_link import ReferralLink
from api.models.purchase import Purchase
from api.models.coin_bonus_ledger import CoinBonusLedger
from api.models.partner_commission_ledger import PartnerCommissionLedger
from api.models.partner_balance import PartnerBalance
from api.models.payout_request import PayoutRequest
from api.models.audit_log import AuditLog
from api.models.transaction import Transaction
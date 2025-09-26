import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.transaction import Transaction

async def create_transaction(db: AsyncSession, partner_id: uuid.UUID, amount: float, transaction_type: str):
    db_transaction = Transaction(
        partner_id=partner_id,
        amount=amount,
        transaction_type=transaction_type
    )
    db.add(db_transaction)
    await db.commit()
    await db.refresh(db_transaction)
    return db_transaction
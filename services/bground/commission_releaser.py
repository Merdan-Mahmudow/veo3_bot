import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

from api.models import PartnerCommissionLedger, PartnerBalance, User
from api.models.partner_commission_ledger import CommissionStatus
from api.database import get_async_session # Assuming celery can get a session
# This file should be imported in a place where the Celery app is initialized
# to ensure the task is registered.
# from services.celery_app import app

# In a production setup, this task would be scheduled to run periodically,
# for example, once every hour, using Celery Beat.
# Example Celery Beat schedule configuration:
# app.conf.beat_schedule = {
#     'release-commissions-every-hour': {
#         'task': 'release_held_commissions',
#         'schedule': 3600.0,  # Run every hour
#     },
# }

# @app.task(name="release_held_commissions")
async def release_held_commissions():
    """
    A periodic Celery task to release commissions from hold to available balance.
    """
    logging.info("Starting commission release task...")
    session: AsyncSession = get_async_session() # Simplified session getting

    try:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        # Find commissions that are on hold and older than 7 days
        # Also join with the User table to check the 'is_suspicious' flag
        held_commissions_stmt = (
            select(PartnerCommissionLedger)
            .join(User, PartnerCommissionLedger.user_id == User.id)
            .where(
                PartnerCommissionLedger.status == CommissionStatus.hold,
                PartnerCommissionLedger.created_at <= seven_days_ago,
                User.is_suspicious == False
            )
        )

        held_commissions_result = await session.execute(held_commissions_stmt)
        commissions_to_release = held_commissions_result.scalars().all()

        if not commissions_to_release:
            logging.info("No commissions to release.")
            return

        for commission in commissions_to_release:
            try:
                # Use a nested transaction for each commission to ensure atomicity
                async with session.begin_nested():
                    partner_balance = await session.get(PartnerBalance, commission.partner_id, with_for_update=True)
                    if not partner_balance:
                        logging.error(f"PartnerBalance not found for partner {commission.partner_id}. Skipping commission {commission.id}")
                        continue

                    # Move funds from hold to available
                    partner_balance.hold_minor -= commission.commission_minor
                    partner_balance.balance_minor += commission.commission_minor

                    # Update commission status
                    commission.status = CommissionStatus.available

                logging.info(f"Released commission {commission.id} for partner {commission.partner_id} amount {commission.commission_minor}")

            except Exception as e:
                logging.error(f"Failed to process commission {commission.id} for partner {commission.partner_id}: {e}")
                # The nested transaction will rollback, so we can continue with the next one

        await session.commit()
        logging.info(f"Successfully released {len(commissions_to_release)} commissions.")

    except Exception as e:
        logging.error(f"An error occurred during the commission release task: {e}", exc_info=True)
        await session.rollback()
    finally:
        await session.close()
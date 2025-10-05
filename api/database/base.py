from sqlalchemy.orm import declarative_base

# Define the declarative base
Base = declarative_base()

# Import all the models, so that Base has them before being
# imported by Alembic.
# This ensures that Alembic's autogenerate can "see" the models.
from api.models.user import User  # noqa
from api.models.referral import *  # noqa
from api.models.tasks import * # noqa
from api.models.payment import * # noqa
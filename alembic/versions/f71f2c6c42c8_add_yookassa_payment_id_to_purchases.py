"""Add yookassa_payment_id to purchases

Revision ID: f71f2c6c42c8
Revises: e36f4d12907a
Create Date: 2025-10-04 15:52:59.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f71f2c6c42c8'
down_revision: Union[str, Sequence[str], None] = 'e36f4d12907a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('purchases', sa.Column('yookassa_payment_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_purchases_yookassa_payment_id'), 'purchases', ['yookassa_payment_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_purchases_yookassa_payment_id'), table_name='purchases')
    op.drop_column('purchases', 'yookassa_payment_id')
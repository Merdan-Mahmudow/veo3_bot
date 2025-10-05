"""Add pending_payments table

Revision ID: e36f4d12907a
Revises: 4d2b2a043135
Create Date: 2025-10-04 15:24:48.530438

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e36f4d12907a'
down_revision: Union[str, Sequence[str], None] = '4d2b2a043135'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pending_payments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('yookassa_payment_id', sa.String(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('amount_minor', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pending_payments_yookassa_payment_id'), 'pending_payments', ['yookassa_payment_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_pending_payments_yookassa_payment_id'), table_name='pending_payments')
    op.drop_table('pending_payments')
"""Add link_requests table

Revision ID: 7d8be18f7fb8
Revises: f71f2c6c42c8
Create Date: 2025-10-04 16:05:15.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d8be18f7fb8'
down_revision: Union[str, Sequence[str], None] = 'f71f2c6c42c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('link_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('partner_id', sa.UUID(), nullable=False),
    sa.Column('requested_percent', sa.Integer(), nullable=False),
    sa.Column('comment', sa.String(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='link_request_status'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_by_admin_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['partner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['processed_by_admin_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('link_requests')
"""Implement corrected referral schema

Revision ID: c5f8e3a2b1d0
Revises: 3070f7e7841f
Create Date: 2025-09-27 06:30:25.123456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5f8e3a2b1d0'
down_revision = '3070f7e7841f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### Create all new tables for the referral system ###
    op.create_table('roles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_table('purchases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('yookassa_payment_id', sa.String(), nullable=False),
        sa.Column('amount_minor', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(), server_default='RUB', nullable=False),
        sa.Column('is_first_for_user', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('yookassa_payment_id')
    )
    op.create_table('referral_links',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('link_type', sa.Enum('user', 'partner', name='linktype'), nullable=False),
        sa.Column('percent', sa.Integer(), nullable=True),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('comment', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    op.create_table('referrals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('new_user_id', sa.UUID(), nullable=False),
        sa.Column('referrer_type', sa.Enum('user', 'partner', name='referrertype'), nullable=False),
        sa.Column('referrer_id', sa.UUID(), nullable=False),
        sa.Column('ref_link_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['new_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['ref_link_id'], ['referral_links.id']),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('new_user_id')
    )
    op.create_table('audit_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('entity', sa.String(), nullable=False),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('partner_balances',
        sa.Column('partner_id', sa.UUID(), nullable=False),
        sa.Column('balance_minor', sa.Integer(), server_default='0', nullable=False),
        sa.Column('hold_minor', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['partner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('partner_id')
    )
    op.create_table('payout_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('partner_id', sa.UUID(), nullable=False),
        sa.Column('amount_minor', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('requested', 'approved', 'rejected', 'paid', name='payoutstatus'), nullable=False),
        sa.Column('requisites_json', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['partner_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_roles',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role_id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    op.create_table('coin_bonus_ledger',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('giver_id', sa.UUID(), nullable=False),
        sa.Column('receiver_id', sa.UUID(), nullable=False),
        sa.Column('purchase_id', sa.UUID(), nullable=False),
        sa.Column('coins', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['giver_id'], ['users.id']),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id']),
        sa.ForeignKeyConstraint(['receiver_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('partner_commission_ledger',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('partner_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('purchase_id', sa.UUID(), nullable=False),
        sa.Column('ref_link_id', sa.UUID(), nullable=False),
        sa.Column('base_amount_minor', sa.Integer(), nullable=False),
        sa.Column('percent', sa.Integer(), nullable=False),
        sa.Column('commission_minor', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('accrued', 'hold', 'available', 'paid_out', 'reversed', name='commissionstatus'), nullable=False),
        sa.Column('reason', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['partner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id']),
        sa.ForeignKeyConstraint(['ref_link_id'], ['referral_links.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ### Modify existing users table ###
    op.add_column('users', sa.Column('is_suspicious', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # Drop old, incorrect columns if they exist from a previous failed migration state
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('referrer_type', if_exists=True)
        batch_op.drop_column('referrer_id', if_exists=True)
        batch_op.drop_column('referral_link_id', if_exists=True)
        batch_op.drop_column('first_payment_done', if_exists=True)


def downgrade() -> None:
    # ### Revert modifications to users table ###
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('first_payment_done', sa.BOOLEAN(), server_default=sa.text('false'), nullable=False))
        batch_op.add_column(sa.Column('referral_link_id', sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column('referrer_id', sa.UUID(), nullable=True))
        batch_op.add_column(sa.Column('referrer_type', sa.VARCHAR(length=7), nullable=True))
        batch_op.drop_column('is_suspicious')

    # ### Drop all new tables ###
    op.drop_table('partner_commission_ledger')
    op.drop_table('coin_bonus_ledger')
    op.drop_table('user_roles')
    op.drop_table('payout_requests')
    op.drop_table('partner_balances')
    op.drop_table('audit_log')
    op.drop_table('referrals')
    op.drop_table('referral_links')
    op.drop_table('purchases')
    op.drop_table('roles')
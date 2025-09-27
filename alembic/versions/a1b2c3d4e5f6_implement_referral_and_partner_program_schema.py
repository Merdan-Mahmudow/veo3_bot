"""Implement referral and partner program schema

Revision ID: a1b2c3d4e5f6
Revises: 3070f7e7841f
Create Date: 2025-09-27 06:03:50.123456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '3070f7e7841f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### Manually written migration ###
    op.create_table('roles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('purchases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('amount_minor', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('referral_links',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('link_type', sa.Enum('user', 'partner', name='linktype'), nullable=False),
    sa.Column('percent', sa.Integer(), nullable=True),
    sa.Column('token', sa.String(), nullable=False),
    sa.Column('comment', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token')
    )
    op.create_table('audit_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('entity', sa.String(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('payload_json', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('partner_balances',
    sa.Column('partner_id', sa.UUID(), nullable=False),
    sa.Column('balance_minor', sa.Integer(), server_default='0', nullable=False),
    sa.Column('hold_minor', sa.Integer(), server_default='0', nullable=False),
    sa.ForeignKeyConstraint(['partner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('partner_id')
    )
    op.create_table('payout_requests',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('partner_id', sa.UUID(), nullable=False),
    sa.Column('amount_minor', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('requested', 'approved', 'rejected', 'paid', name='payoutstatus'), nullable=False),
    sa.Column('requisites_json', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['partner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_roles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id', 'role_id')
    )
    op.create_table('coin_bonus_ledger',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('giver_id', sa.UUID(), nullable=False),
    sa.Column('receiver_id', sa.UUID(), nullable=False),
    sa.Column('purchase_id', sa.UUID(), nullable=False),
    sa.Column('coins', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['giver_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ),
    sa.ForeignKeyConstraint(['receiver_id'], ['users.id'], ),
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
    sa.ForeignKeyConstraint(['partner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['purchase_id'], ['purchases.id'], ),
    sa.ForeignKeyConstraint(['ref_link_id'], ['referral_links.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('users', sa.Column('referrer_type', sa.Enum('user', 'partner', name='referrertype'), nullable=True))
    op.alter_column('users', 'chat_id', existing_type=sa.VARCHAR(), unique=True, nullable=False)
    op.add_column('users', sa.Column('referral_link_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_users_referral_link_id', 'users', 'referral_links', ['referral_link_id'], ['id'])

    op.drop_table('partners')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### Manually written migration ###
    op.create_table('partners',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('user_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('is_verified', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.Column('balance', sa.NUMERIC(precision=10, scale=2), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='partners_user_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='partners_pkey')
    )
    op.drop_constraint('fk_users_referral_link_id', 'users', type_='foreignkey')
    op.drop_column('users', 'referral_link_id')
    op.alter_column('users', 'chat_id', existing_type=sa.VARCHAR(), unique=False, nullable=False)
    op.drop_column('users', 'referrer_type')
    op.drop_table('partner_commission_ledger')
    op.drop_table('coin_bonus_ledger')
    op.drop_table('user_roles')
    op.drop_table('payout_requests')
    op.drop_table('partner_balances')
    op.drop_table('audit_log')
    op.drop_table('referral_links')
    op.drop_table('purchases')
    op.drop_table('roles')
    # ### end Alembic commands ###